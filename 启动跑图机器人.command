#!/bin/bash
echo "正在启动 Gemini 多账号自动生图工具..."
echo "请保持此终端窗口打开，不要关闭！"
cd "$(dirname "$0")"
python3 main.py
