@echo off
chcp 65001 >nul
echo 正在启动 Gemini 多账号自动生图工具...
echo 请保持此黑色窗口打开，不要关闭！
cd /d "%~dp0"
python main.py
pause
