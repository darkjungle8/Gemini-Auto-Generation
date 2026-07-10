#!/bin/bash
echo "正在为您安装 Python 运行环境所需的依赖包..."
cd "$(dirname "$0")"
pip3 install setuptools
pip3 install --no-cache-dir -r requirements.txt
echo ""
echo "安装完成！您可以双击“启动跑图机器人.command”来运行程序了。"
