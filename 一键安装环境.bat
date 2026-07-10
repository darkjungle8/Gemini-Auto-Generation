@echo off
chcp 65001 >nul
echo 正在为您安装 Python 运行环境所需的依赖包...
cd /d "%~dp0"
pip install setuptools
pip install --no-cache-dir -r requirements.txt
echo.
echo 安装完成！您可以双击“启动跑图机器人.bat”来运行程序了。
pause
