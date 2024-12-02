from webdriver_manager.chrome import ChromeDriverManager

def download_chromedriver():
    """下载 ChromeDriver 到当前目录"""
    try:
        driver_path = ChromeDriverManager().install()
        print(f"ChromeDriver 已下载到: {driver_path}")
        return True
    except Exception as e:
        print(f"下载 ChromeDriver 失败: {str(e)}")
        return False

if __name__ == "__main__":
    download_chromedriver() 