from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
import os
import time
import threading
import sys
import shutil
from select import select

# 添加用户数据目录的常量
USER_DATA_DIR = "./chrome_user_data"

def read_urls(file_path='url.txt'):
    """读取URL文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f.readlines() if line.strip()]
    return urls

def setup_browser(use_previous_session=False):
    """设置浏览器配置"""
    chrome_options = Options()
    
    # 设置为 1179×2490 的等比例缩小尺寸
    target_width = 450
    original_ratio = 2490 / 1179
    target_height = int(target_width * original_ratio)
    
    mobile_emulation = {
        "deviceMetrics": {
            "width": target_width,
            "height": target_height,
            "pixelRatio": 2.0,
            "mobile": True
        }
    }
    chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    
    # 如果选择使用上次会话，添加用户数据目录
    if use_previous_session and os.path.exists(USER_DATA_DIR):
        chrome_options.add_argument(f'user-data-dir={USER_DATA_DIR}')
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(target_width, target_height)
    
    return driver

def save_browser_session(driver):
    """保存浏览器会话信息"""
    try:
        # 确保目录存在
        if os.path.exists(USER_DATA_DIR):
            shutil.rmtree(USER_DATA_DIR)
        
        # 获取源目录
        chrome_temp_dir = driver.capabilities['chrome']['userDataDir']
        
        def ignore_files(dir, files):
            """忽略特定文件"""
            return [
                f for f in files
                if f.startswith('Singleton') or  # 忽略 Singleton 相关文件
                f == 'RunningChromeVersion' or   # 忽略版本文件
                f.endswith('.sock') or           # 忽略 socket 文件
                f.endswith('.lock')              # 忽略锁文件
            ]
        
        # 使用 ignore 参数复制目录
        shutil.copytree(
            chrome_temp_dir, 
            USER_DATA_DIR, 
            ignore=ignore_files,
            dirs_exist_ok=True
        )
        
        print("浏览器会话信息已保存")
        return True
        
    except Exception as e:
        print(f"保存浏览器会话信息失败: {str(e)}")
        # 如果保存失败，尝试清理已创建的目录
        if os.path.exists(USER_DATA_DIR):
            try:
                shutil.rmtree(USER_DATA_DIR)
            except:
                pass
        return False

def ask_yes_no(question, default=True):
    """询问用户是否确认，带默认选项"""
    default_hint = "(Y/n)" if default else "(y/N)"
    while True:
        response = input(f"{question} {default_hint}: ").lower().strip()
        if not response:  # 如果用户直接按回车，使用默认值
            return default
        if response in ['y', 'yes']:
            return True
        if response in ['n', 'no']:
            return False
        print("请输入 y 或 n，或直接按回车使用默认选项")

def wait_for_login(driver, timeout=60):
    """等待用户登录"""
    print(f"请在{timeout}秒内完成登录，或按Enter键继续...")
    print("正在打开小红书登录页面...")
    driver.get("https://www.xiaohongshu.com")
    
    # 创建一个超时事件
    start_time = time.time()
    
    def check_input():
        input()
        return True
    
    # 创建输入检查线程
    input_thread = threading.Thread(target=check_input)
    input_thread.daemon = True
    input_thread.start()
    
    # 等待直到超时或输入
    while True:
        if not input_thread.is_alive():  # 如果用户按下Enter键
            print("检测到Enter键，继续执行...")
            break
        if time.time() - start_time > timeout:  # 如果超时
            print("等待登录超时，继续执行...")
            break
        time.sleep(0.1)

def capture_screenshots():
    """主函数：捕获截图"""
    # 询问是否使用上次的会话（默认使用）
    use_previous = False
    if os.path.exists(USER_DATA_DIR):
        use_previous = ask_yes_no("检测到上次的浏览器配置，是否使用？", default=True)
    
    # 创建截图目录
    os.makedirs('./screenshot', exist_ok=True)
    
    # 读取URL列表
    urls = read_urls()
    if not urls:
        print("URL文件为空或不存在")
        return
    
    # 预先加载顶部和底部图片
    try:
        top_img = Image.open("src/top.jpg")
        bottom_img = Image.open("src/bottom.jpg")
        if top_img.size != (1179, 165) or bottom_img.size != (1179, 101):
            print("错误：顶部或底部图片尺寸不正确")
            return
    except Exception as e:
        print(f"加载顶部或底部图片失败: {str(e)}")
        return
    
    # 设置浏览器
    driver = setup_browser(use_previous)
    
    try:
        # 如果不使用上次会话，则需要等待登录
        if not use_previous:
            wait_for_login(driver)
        
        # 遍历URL并截图
        for i, url in enumerate(urls, 1):
            try:
                print(f"正在处理第 {i} 个URL: {url}")
                driver.get(url)
                
                # 等待页面加载完成
                time.sleep(3)
                
                # 临时截图路径
                temp_screenshot_path = f'./screenshot/temp_{i}_1.png'
                final_screenshot_path = f'./screenshot/{i}_1.png'
                
                # 保存原始截图
                driver.save_screenshot(temp_screenshot_path)
                
                # 打开图片并进行处理
                with Image.open(temp_screenshot_path) as img:
                    # 调整主截图尺寸
                    resized_img = img.resize((1179, 2490), Image.Resampling.LANCZOS)
                    # 裁切时去掉上面195px(180+15)和下面5px
                    cropped_img = resized_img.crop((0, 195, 1179, 2485))
                    
                    # 创建最终尺寸的空白图片 (1179 × 2556)
                    final_img = Image.new('RGB', (1179, 2556), 'white')
                    
                    # 拼接顺序：
                    # 顶部图片(165px) + 主截图(2290px) + 底部图片(101px)
                    final_img.paste(top_img, (0, 0))  # 顶部图片
                    final_img.paste(cropped_img, (0, 165))  # 主截图
                    final_img.paste(bottom_img, (0, 2455))  # 底部图片位置调整
                    
                    # 保存最终图片
                    final_img.save(final_screenshot_path, quality=95)
                
                # 删除临时文件
                os.remove(temp_screenshot_path)
                
                print(f"截图已保存并处理: {final_screenshot_path}")
                
            except Exception as e:
                print(f"处理URL时出错: {url}")
                print(f"错误信息: {str(e)}")
                continue
        
        # 只有在没有使用历史配置时才询问是否保存
        if not use_previous:
            if ask_yes_no("是否保存当前的浏览器配置（包含登录状态等）？", default=True):
                save_browser_session(driver)
                
    finally:
        driver.quit()
        # 关闭图片
        top_img.close()
        bottom_img.close()

def prepare_bottom_image():
    """准备底部图片资源"""
    print("正在准备底部图片资源...")
    bottom_path = "src/bottom.jpg"
    
    try:
        # 检查目录是否存在并确保有写权限
        os.makedirs("src", exist_ok=True)
        
        # 检查文件是否存在
        if not os.path.exists(bottom_path):
            print(f"错误：底部图片不存在 ({bottom_path})")
            return False
            
        # 检查文件权限
        if not os.access(bottom_path, os.W_OK):
            print(f"错误：没有文件的写入权限 ({bottom_path})")
            print("尝试修改文件权限...")
            try:
                # 尝试修改文件权限为可写
                os.chmod(bottom_path, 0o666)
            except Exception as e:
                print(f"修改文件权限失败: {str(e)}")
                print("建议手动检查文件权限或以管理员权限运行程序")
                return False
        
        # 处理图片
        with Image.open(bottom_path) as img:
            width, height = img.size
            
            # 检查尺寸是否已经符合要求 (现在是101px而不是96px)
            if width == 1179 and height == 101:
                print("底部图片尺寸正确")
                return True
            
            print(f"调整底部图片尺寸 (当前: {width}×{height} -> 目标: 1179×101)")
            
            # 计算等比例缩放后的高度
            scale_ratio = 1179 / width
            new_height = int(height * scale_ratio)
            
            # 先调整宽度到 1179
            resized_img = img.resize((1179, new_height), Image.Resampling.LANCZOS)
            
            # 从底部裁切 101 像素（96+5）
            final_img = resized_img.crop((0, new_height - 101, 1179, new_height))
            
            try:
                # 尝试先保存到临时文件
                temp_path = "src/bottom_temp.jpg"
                final_img.save(temp_path, quality=95)
                
                # 如果临时文件保存成功，则替换原文件
                shutil.move(temp_path, bottom_path)
                print("底部图片已调整到正确尺寸")
                return True
            except Exception as e:
                print(f"保存图片失败: {str(e)}")
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                return False
            
    except PermissionError:
        print(f"权限错误：无法访问或修改文件 ({bottom_path})")
        print("请检查文件权限或以管理员权限运行程序")
        return False
    except Exception as e:
        print(f"处理底部图片时出错: {str(e)}")
        return False

def prepare_top_image():
    """准备顶部图片资源"""
    print("正在准备顶部图片资源...")
    top_path = "src/top.jpg"
    
    try:
        # 检查目录是否存在并确保有写权限
        os.makedirs("src", exist_ok=True)
        
        # 检查文件是否存在
        if not os.path.exists(top_path):
            print(f"错误：顶部图片不存在 ({top_path})")
            return False
            
        # 检查文件权限
        if not os.access(top_path, os.W_OK):
            print(f"错误：没有文件的写入权限 ({top_path})")
            print("尝试修改文件权限...")
            try:
                # 尝试修改文件权限为可写
                os.chmod(top_path, 0o666)
            except Exception as e:
                print(f"修改文件权限失败: {str(e)}")
                print("建议手动检查文件权限或以管理员权限运行程序")
                return False
        
        # 处理图片
        with Image.open(top_path) as img:
            width, height = img.size
            
            # 检查尺寸是否已经符合要求（现在是165px而不是150px）
            if width == 1179 and height == 165:
                print("顶部图片尺寸正确")
                return True
            
            print(f"调整顶部图片尺寸 (当前: {width}×{height} -> 目标: 1179×165)")
            
            # 计算等比例缩放后的高度
            scale_ratio = 1179 / width
            new_height = int(height * scale_ratio)
            
            # 先调整宽度到 1179
            resized_img = img.resize((1179, new_height), Image.Resampling.LANCZOS)
            
            # 从顶部裁切 165 像素（150+15）
            final_img = resized_img.crop((0, 0, 1179, 165))
            
            try:
                # 尝试先保存到临时文件
                temp_path = "src/top_temp.jpg"
                final_img.save(temp_path, quality=95)
                
                # 如果临时文件保存成功，则替换原文件
                shutil.move(temp_path, top_path)
                print("顶部图片已调整到正确尺寸")
                return True
            except Exception as e:
                print(f"保存图片失败: {str(e)}")
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                return False
            
    except PermissionError:
        print(f"权限错误：无法访问或修改文件 ({top_path})")
        print("请检查文件权限或以管理员权限运行程序")
        return False
    except Exception as e:
        print(f"处理顶部图片时出错: {str(e)}")
        return False

if __name__ == "__main__":
    # 准备资源
    prepare_top_image()
    prepare_bottom_image()
    
    # 开始主程序
    capture_screenshots()
