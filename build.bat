@echo off
echo Installing requirements...
pip install -r requirements.txt

echo Downloading ChromeDriver...
python download_chromedriver.py

echo Building application...
python build.py

echo Build complete!
pause 