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

if __name__ == '__main__':
    # 确保工作目录正确
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    
    # 创建必要的目录
    os.makedirs('screenshot', exist_ok=True)
    os.makedirs('src', exist_ok=True)
    
    # 启动应用
    web.app.run(host='0.0.0.0', port=web.find_available_port())
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
        f'--hidden-import webdriver_manager '
        f'--hidden-import selenium '
        f'--collect-data PIL '
        f'--collect-all requests '
        f'--collect-all webdriver_manager '
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
start /B XHS_Screenshot.exe
start http://127.0.0.1:5000
"""
        with open("dist/启动程序.bat", "w", encoding="utf-8") as f:
            f.write(launcher_script)

if __name__ == "__main__":
    try:
        build()
        print("打包完成！")
    except Exception as e:
        print(f"打包过程中出错: {str(e)}")
        input("按回车键继续...") 