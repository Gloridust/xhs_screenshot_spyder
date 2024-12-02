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
import json
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)
CORS(app)  # 启用 CORS

# 全局变量
output_queue = Queue()
current_driver = None
processing = False
login_confirmed = Event()
chrome_service = None

# 添加资源URL配置
RESOURCE_BASE_URL = "https://github.com/Gloridust/xhs_screenshot_spyder/blob/main/src/"
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

def check_resources():
    """检查必要的资源文件"""
    required_resources = [
        "src/top.jpg",
        "src/bottom.jpg",
        "src/example_real.jpg"
    ]
    
    missing_files = []
    for file_path in required_resources:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        error_msg = "缺少必要的资源文件:\n"
        for file in missing_files:
            error_msg += f"- {file}\n"
        error_msg += "\n请确保这些文件存在于正确的位置。"
        return False, error_msg
    
    return True, "资源文件检查通过"

def init_chrome_driver():
    """初始化 ChromeDriver"""
    global chrome_service
    try:
        output_queue.put("开始初始化浏览器环境...")
        output_queue.put("1. 检查 Chrome 浏览器...")
        
        # 使用更简单的初始化方式
        try:
            driver_path = ChromeDriverManager().install()
        except Exception as e:
            # 如果自动安装失败，尝试使用系统中已有的 ChromeDriver
            output_queue.put(f"自动下载 ChromeDriver 失败: {str(e)}")
            output_queue.put("尝试查找系统中已安装的 ChromeDriver...")
            
            # 在常见位置查找 ChromeDriver
            possible_paths = [
                "chromedriver",  # PATH 中的 ChromeDriver
                "/usr/local/bin/chromedriver",  # macOS/Linux 常见位置
                "C:\\Program Files\\ChromeDriver\\chromedriver.exe",  # Windows 常见位置
                "./chromedriver.exe",  # 当前目录
            ]
            
            driver_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    driver_path = path
                    break
            
            if not driver_path:
                raise Exception("未找到可用的 ChromeDriver")
        
        output_queue.put("2. 配置 ChromeDriver 服务...")
        chrome_service = Service(driver_path)
        
        output_queue.put("✓ 浏览器环境初始化完成")
        return True
        
    except Exception as e:
        error_msg = f"ChromeDriver 初始化失败: {str(e)}"
        output_queue.put(error_msg)
        output_queue.put("\n请检查:")
        output_queue.put("1. Chrome 浏览器是否正确安装")
        output_queue.put("2. 网络连接是否正常")
        output_queue.put("3. 是否有足够的磁盘空间")
        output_queue.put("\n如果问题持续，请手动下载 ChromeDriver:")
        output_queue.put("1. 访问 https://chromedriver.chromium.org/downloads")
        output_queue.put("2. 下载与您的 Chrome 浏览器版本匹配的 ChromeDriver")
        output_queue.put("3. 解压并将 chromedriver 放在程序所在目录")
        return False

@app.route('/')
def index():
    # 检查是否存在浏览器配置
    has_config = os.path.exists("./chrome_user_data")
    return render_template('index.html', has_config=has_config)

@app.route('/start_process', methods=['POST'])
def start_process():
    """开始处理截图"""
    global current_driver, processing, chrome_service
    
    if processing:
        return jsonify({
            'success': False,
            'message': '已有任务正在进行中'
        })
    
    # 检查 ChromeDriver 是否已准备好
    if chrome_service is None:
        output_queue.put("ChromeDriver 未就绪，正在重新初始化...")
        if not init_chrome_driver():
            return jsonify({
                'success': False,
                'message': 'ChromeDriver 初始化失败，请查看控制台输出'
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
                
                # 设置浏览器，使用全局的 chrome_service
                current_driver = setup_browser(use_previous, chrome_service)
                output_queue.put("浏览器已启动")
                
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
                
                # 更新状态为正在截图
                output_queue.put("状态更新: 正在截图中...")
                
                # 遍历URL并截图
                for i, url in enumerate(urls, 1):
                    process_single_url(current_driver, url, i, top_img, bottom_img, back_icon)
                
                # 总是保存会话
                save_browser_session(current_driver)
                output_queue.put("已保存浏览器配置，下次可以直接使用")
                
                # 更新状态为已完成
                output_queue.put("状态更新: 已完成")
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
        'message': '正在启动浏览器...'
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
        # 检查资源文件
        success, message = check_resources()
        if not success:
            print(message)
            return jsonify({
                'success': False,
                'messages': output_reader()
            })
        
        # 处理资源
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
    """检查是否存在有效的浏览器配置"""
    try:
        # 检查 cookie 文件是否存在
        cookie_file = "./chrome_user_data/cookies.json"
        if not os.path.exists(cookie_file):
            return jsonify({
                'has_config': False,
                'message': '未找到配置文件'
            })
            
        # 检查 cookie 文件是否有效
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
                
            # 检查是否有有效的 cookie
            if not cookies or not isinstance(cookies, list) or len(cookies) == 0:
                return jsonify({
                    'has_config': False,
                    'message': 'Cookie 文件无效'
                })
                
            # 检查必要的 cookie 字段
            required_fields = ['name', 'value', 'domain']
            for cookie in cookies:
                if not all(field in cookie for field in required_fields):
                    return jsonify({
                        'has_config': False,
                        'message': 'Cookie 格式无效'
                    })
            
            return jsonify({
                'has_config': True,
                'message': '找到有效的配置'
            })
            
        except (json.JSONDecodeError, IOError) as e:
            return jsonify({
                'has_config': False,
                'message': f'Cookie 文件读取失败: {str(e)}'
            })
            
    except Exception as e:
        return jsonify({
            'has_config': False,
            'message': f'检查配置时出错: {str(e)}'
        })

@app.route('/stop_process', methods=['POST'])
def stop_process():
    """停止当前处理"""
    global current_driver, processing
    try:
        # 设置停止标志
        processing = False
        
        # 清除登录确认状态
        login_confirmed.clear()
        
        # 关闭浏览器
        if current_driver:
            try:
                current_driver.quit()
            except Exception as e:
                print(f"关闭浏览器时出错: {str(e)}")
            finally:
                current_driver = None
        
        # 清理输出队列
        while not output_queue.empty():
            output_queue.get()
            
        # 添加停止消息到输出
        output_queue.put("\n⚠️ 任务已停止")
        
        return jsonify({
            'success': True,
            'message': '已停止处理'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'停止处理时出错: {str(e)}'
        })

if __name__ == '__main__':
    try:
        # 查找可用端口
        port = find_available_port()
        output_queue.put(f"使用端口: {port}")
        
        # 在启动浏览器前初始化 ChromeDriver
        init_success = init_chrome_driver()
        if not init_success:
            output_queue.put("⚠️ ChromeDriver 初始化失败，程序可能无法正常运行")
        
        # 启动浏览器（只启动一次）
        url = f'http://127.0.0.1:{port}'
        webbrowser.open_new(url)
        
        # 启动Flask应用
        app.run(debug=False, port=port, host='0.0.0.0')
    except Exception as e:
        output_queue.put(f"启动服务器失败: {str(e)}")
        input("按回车键退出...")
