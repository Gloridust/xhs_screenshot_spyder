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
from threading import Thread
import time
import webbrowser
import subprocess
import platform
import shutil
import socket

app = Flask(__name__)
CORS(app)  # 启用 CORS

# 全局变量
output_queue = Queue()
current_driver = None
processing = False

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
                
                # 遍历URL并截图
                for i, url in enumerate(urls, 1):
                    process_single_url(current_driver, url, i, top_img, bottom_img, back_icon)
                
                # 保存会话（如果需要）
                if not use_previous:
                    save_browser_session(current_driver)
                
                output_queue.put("\n✨ 任务完成！所有截图已保存。")
                    
            finally:
                if current_driver:
                    current_driver.quit()
                    current_driver = None
                processing = False
    
    # 启动处理线程
    Thread(target=process_task, daemon=True).start()
    
    return jsonify({
        'success': True,
        'message': '任务已启动'
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
    # 添加必要的 CORS 头部和安全检查
    response = send_from_directory('screenshot', filename)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

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
