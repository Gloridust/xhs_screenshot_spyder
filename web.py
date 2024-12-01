from flask_cors import CORS
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from main import (
    setup_browser, save_browser_session, prepare_top_image,
    prepare_bottom_image, prepare_back_icon, process_single_url
)
from PIL import Image
import os
import sys
import io
from queue import Queue
from threading import Thread, Event
import time
import webbrowser
import subprocess
import platform
import shutil
import socket
import requests
from urllib.parse import urljoin

app = Flask(__name__)
CORS(app)  # 启用 CORS

# 全局变量
output_queue = Queue()
current_driver = None
processing = False
login_confirmed = Event()

# 添加资源URL配置
RESOURCE_BASE_URL = "https://raw.githubusercontent.com/Gloridust/xhs_screenshot_spyder/main/src/"
REQUIRED_RESOURCES = {
    "top.jpg": "top.jpg",
    "bottom.jpg": "bottom.jpg",
    "example_real.jpg": "example_real.jpg"
}

def open_folder(path):
    """跨平台打开文件夹"""
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":  # macOS
        subprocess.run(["open", path])
    else:  # Linux
        subprocess.run(["xdg-open", path])

def output_reader():
    """读取输出队列并返回内容"""
    messages = []
    while not output_queue.empty():
        messages.append(output_queue.get_nowait())
    return messages

class OutputCapture:
    """捕获 print 输出的上下文管理器"""
    def __init__(self):
        self.original_stdout = sys.stdout
        self.output = io.StringIO()

    def write(self, text):
        self.output.write(text)
        if text.strip():  # 只有非空内容才放入队列
            output_queue.put(text)

    def flush(self):
        pass

    def __enter__(self):
        sys.stdout = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.original_stdout

def download_resource(filename):
    """从GitHub下载资源文件"""
    url = urljoin(RESOURCE_BASE_URL, filename)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # 确保src目录存在
        os.makedirs("src", exist_ok=True)
        
        # 保存文件
        file_path = os.path.join("src", filename)
        with open(file_path, "wb") as f:
            f.write(response.content)
        print(f"已下载资源文件: {filename}")
        return True
    except Exception as e:
        print(f"下载资源文件失败 {filename}: {str(e)}")
        return False

def check_and_download_resources():
    """检查并下载缺失的资源文件"""
    missing_resources = []
    for filename in REQUIRED_RESOURCES.keys():
        file_path = os.path.join("src", filename)
        if not os.path.exists(file_path):
            missing_resources.append(filename)
    
    if missing_resources:
        print("检测到缺失的资源文件，正在从GitHub下载...")
        for filename in missing_resources:
            download_resource(filename)

@app.route('/')
def index():
    # 检查是否存在浏览器配置
    has_config = os.path.exists("./chrome_user_data")
    return render_template('index.html', has_config=has_config)

@app.route('/start_process', methods=['POST'])
def start_process():
    """开始处理截图"""
    global current_driver, processing
    
    if processing:
        return jsonify({
            'success': False,
            'message': '已有任务正在进行中'
        })
    
    use_previous = request.json.get('use_previous', False)
    urls = request.json.get('urls', '').strip().split('\n')
    urls = [url.strip() for url in urls if url.strip()]
    
    if not urls:
        return jsonify({
            'success': False,
            'message': '请输入有效的URL列表'
        })
    
    def process_task():
        global current_driver, processing
        processing = True
        
        with OutputCapture():
            try:
                # 预先加载图片资源
                try:
                    top_img = Image.open("src/top.jpg")
                    bottom_img = Image.open("src/bottom.jpg")
                    back_icon = Image.open("src/back.png")
                except Exception as e:
                    output_queue.put(f"加载图片资源失败: {str(e)}")
                    return
                
                # 设置浏览器
                current_driver = setup_browser(use_previous)
                
                # 如果不使用上次配置，需要等待登录
                if not use_previous:
                    output_queue.put("\n请在浏览器中完成登录，然后点击下方的【确认已登录】按钮继续...")
                    # 打开小红书登录页面
                    current_driver.get("https://www.xiaohongshu.com")
                    # 等待登录确认信号
                    while not login_confirmed.is_set():
                        time.sleep(0.5)
                        if not processing:  # 如果处理被终止
                            return
                    output_queue.put("已确认登录，开始处理...")
                
                # 遍历URL并截图
                for i, url in enumerate(urls, 1):
                    process_single_url(current_driver, url, i, top_img, bottom_img, back_icon)
                
                # 总是保存会话
                save_browser_session(current_driver)
                output_queue.put("已保存浏览器配置，下次可以直接使用")
                
                output_queue.put("\n✨ 任务完成！所有截图已保存。")
                    
            finally:
                if current_driver:
                    current_driver.quit()
                    current_driver = None
                processing = False
                login_confirmed.clear()  # 重置登录确认状态
    
    # 启动处理线程
    Thread(target=process_task, daemon=True).start()
    
    return jsonify({
        'success': True,
        'message': '任务已启动'
    })

@app.route('/confirm_login', methods=['POST'])
def confirm_login():
    """确认登录完成"""
    login_confirmed.set()
    return jsonify({
        'success': True,
        'message': '已确认登录'
    })

@app.route('/open_output_folder', methods=['POST'])
def open_output_folder():
    """打开输出文件夹"""
    folder_path = os.path.abspath('./screenshot')
    try:
        open_folder(folder_path)
        return jsonify({
            'success': True,
            'message': '已打开输出文件夹'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'打开文件夹失败: {str(e)}'
        })

@app.route('/clear_workspace', methods=['POST'])
def clear_workspace():
    """清空工作区"""
    try:
        # 清空 screenshot 文件夹中的所有文件
        folder_path = './screenshot'
        for filename in os.listdir(folder_path):
            if filename != '.gitkeep':  # 保留 .gitkeep 文件
                file_path = os.path.join(folder_path, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(f'删除文件失败: {str(e)}')
        return jsonify({
            'success': True,
            'message': '工作区已清空'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'清空工作区失败: {str(e)}'
        })

@app.route('/prepare_resources', methods=['POST'])
def prepare_resources():
    """准备资源文件"""
    with OutputCapture():
        # 首先检查并下载缺失的资源
        check_and_download_resources()
        
        # 然后处理资源
        success = all([
            prepare_top_image(),
            prepare_bottom_image(),
            prepare_back_icon()
        ])
    return jsonify({
        'success': success,
        'messages': output_reader()
    })

@app.route('/get_output')
def get_output():
    """获取输出内容"""
    messages = output_reader()
    return jsonify({
        'messages': messages,
        'processing': processing
    })

@app.route('/get_screenshots')
def get_screenshots():
    """获取已生成的截图列表"""
    screenshots = []
    folder_path = './screenshot'
    for filename in sorted(os.listdir(folder_path)):
        if filename.endswith('.png') and filename != '.gitkeep':
            screenshots.append({
                'filename': filename,
                'path': f'/screenshots/{filename}',
                'timestamp': os.path.getmtime(os.path.join(folder_path, filename))
            })
    return jsonify(screenshots)

# 修改静态文件路由
@app.route('/screenshots/<path:filename>')
def serve_screenshot(filename):
    """服务截图文件"""
    try:
        return send_from_directory(
            os.path.abspath('./screenshot'),
            filename,
            mimetype='image/png',
            as_attachment=False
        )
    except Exception as e:
        print(f"加载图片失败: {str(e)}")
        return '', 404

def find_available_port(start_port=5000, max_attempts=10):
    """查找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        try:
            # 尝试绑定端口
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                # 如果成功绑定，立即关闭socket以释放端口
                s.close()
                return port
        except OSError:
            continue
    raise RuntimeError(f"在端口范围 {start_port}-{start_port + max_attempts - 1} 内未找到可用端口")

@app.route('/check_config')
def check_config():
    """检查是否存在浏览器配置"""
    has_config = os.path.exists("./chrome_user_data")
    return jsonify({
        'has_config': has_config
    })

if __name__ == '__main__':
    try:
        # 查找可用端口
        port = find_available_port()
        print(f"使用端口: {port}")
        
        # 启动浏览器（只启动一次）
        url = f'http://127.0.0.1:{port}'
        webbrowser.open_new(url)  # 使用 open_new 而不是 open
        
        # 启动Flask应用
        app.run(debug=False, port=port, host='0.0.0.0')  # 关闭debug模式
    except Exception as e:
        print(f"启动服务器失败: {str(e)}")
        input("按回车键退出...")
