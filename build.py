import os
import shutil
import sys
from pathlib import Path

def prepare_build():
    """准备构建环境"""
    # 创建构建目录
    build_dir = Path("build_resources")
    build_dir.mkdir(exist_ok=True)
    
    # 复制必要的文件到构建目录
    files_to_copy = [
        "web.py",
        "main.py",
        "requirements.txt"
    ]
    
    for file in files_to_copy:
        shutil.copy2(file, build_dir)
    
    # 复制目录
    dirs_to_copy = [
        "templates",
        "src",
        "screenshot"
    ]
    
    for dir_name in dirs_to_copy:
        src_dir = Path(dir_name)
        dst_dir = build_dir / dir_name
        if src_dir.exists():
            if dst_dir.exists():
                shutil.rmtree(dst_dir)
            shutil.copytree(src_dir, dst_dir)
        else:
            dst_dir.mkdir(exist_ok=True)
            # 为 screenshot 目录创建 .gitkeep
            if dir_name == "screenshot":
                (dst_dir / ".gitkeep").touch()

def create_entry_point():
    """创建启动文件"""
    entry_code = """
import web
import os
import sys
import time
import webbrowser
from web import output_queue

def init_with_progress():
    \"\"\"带进度显示的初始化\"\"\"
    print("正在初始化浏览器环境...")
    print("1. 检查 Chrome 浏览器...")
    
    try:
        print("2. 下载 ChromeDriver...")
        init_success = web.init_chrome_driver()
        if not init_success:
            print("⚠️ ChromeDriver 初始化失败，程序可能无法正常运行")
            return False
        print("✓ 浏览器环境初始化完成")
        return True
    except Exception as e:
        print(f"初始化失败: {str(e)}")
        return False

if __name__ == '__main__':
    try:
        # 确保工作目录正确
        if getattr(sys, 'frozen', False):
            os.chdir(os.path.dirname(sys.executable))
        
        # 创建必要的目录
        os.makedirs('screenshot', exist_ok=True)
        os.makedirs('src', exist_ok=True)
        
        # 在启动 Web 服务前初始化 ChromeDriver
        print("正在准备环境，请稍候...")
        init_success = init_with_progress()
        
        # 获取可用端口
        port = web.find_available_port()
        print(f"使用端口: {port}")
        
        # 启动浏览器（延迟启动，等待服务器准备就绪）
        url = f'http://127.0.0.1:{port}'
        def open_browser():
            time.sleep(1)  # 等待服务器启动
            webbrowser.open_new(url)
        
        import threading
        threading.Thread(target=open_browser, daemon=True).start()
        
        # 启动 Flask 应用
        web.app.run(host='0.0.0.0', port=port)
        
    except Exception as e:
        print(f"启动失败: {str(e)}")
        input("按回车键退出...")
"""
    
    with open("build_resources/run.py", "w", encoding="utf-8") as f:
        f.write(entry_code.strip())

def build():
    """执行构建"""
    # 准备构建环境
    prepare_build()
    create_entry_point()
    
    # 检查是否存在图标文件
    icon_path = Path("src/icon.ico")
    icon_option = f'--icon "{icon_path}" ' if icon_path.exists() else ''
    
    # 根据操作系统决定是否使用 windowed 模式
    import platform
    windowed_option = '--windowed ' if platform.system() == 'Darwin' else ''  # 仅在 macOS 上使用 windowed
    
    # PyInstaller 命令
    cmd = (
        f'pyinstaller --noconfirm --onefile {windowed_option}'
        f'--add-data "build_resources/templates:templates" '
        f'--hidden-import requests '
        f'--hidden-import urllib3 '
        f'--hidden-import PIL '
        f'--hidden-import selenium '
        f'--collect-data PIL '
        f'--collect-all requests '
        f'{icon_option}'
        f'--name "XHS_Screenshot" '
        f'build_resources/run.py'
    )
    
    # 执行打包命令
    os.system(cmd)
    
    # 清理构建文件
    shutil.rmtree("build_resources")

    # 在 Windows 上创建启动脚本
    if platform.system() == 'Windows':
        launcher_script = """@echo off
chcp 65001 > nul
echo [Starting] Starting program, please wait...
start /wait /B XHS_Screenshot.exe
"""
        # 使用 UTF-8 编码写入文件
        with open("dist/启动程序.bat", "w", encoding="utf-8", newline='\n') as f:
            f.write(launcher_script)

if __name__ == "__main__":
    try:
        build()
        print("打包完成！")
    except Exception as e:
        print(f"打包过程中出错: {str(e)}")
        input("按回车键继续...") 