#!/usr/bin/env python3
"""Gemini 多账号自动生图工具 — 程序入口."""

import sys
import os
import logging

# Ensure the project root is on sys.path so that ``import core.*`` etc. work
# regardless of how the script is launched.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)




def setup_logging():
    """Configure root logger to write to both console and a log file."""
    log_dir = os.path.join(PROJECT_ROOT, "logs")
    os.makedirs(log_dir, exist_ok=True)

    from datetime import datetime
    log_file = os.path.join(log_dir, f"run_{datetime.now():%Y%m%d_%H%M%S}.log")

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(fh)
    root_logger.addHandler(ch)

    logging.info(f"日志文件: {log_file}")


def main():
    setup_logging()
    logging.info("启动 Gemini 多账号自动生图工具 (Web UI)")
    
    from web.server import run_app
    run_app()

if __name__ == "__main__":
    main()

