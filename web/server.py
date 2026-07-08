import os
import time
import queue
import logging
import threading
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO

import undetected_chromedriver as uc

from utils.config import Config
from core.task_queue import TaskQueue
from core.account_manager import AccountManager
from core.browser_worker import BrowserWorker

logger = logging.getLogger(__name__)

app = Flask(__name__)
# Allow cross-origin if needed, and async_mode will default to eventlet/gevent/threading
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

config = Config()
task_queue = TaskQueue()
workers = []
log_queue = queue.Queue()

def emit_task_update():
    socketio.emit("task_update", {"tasks": task_queue.get_all_tasks()})

task_queue.on_update = emit_task_update

# ------------------------------------------------------------------
# Background Log Emitter
# ------------------------------------------------------------------

def log_emitter():
    """Continuously poll the log_queue and emit to WebSockets."""
    while True:
        try:
            msg, level = log_queue.get(timeout=1)
            socketio.emit("log_event", {"message": msg, "level": level})
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Emitter error: {e}")
            time.sleep(1)

# Start emitter thread
threading.Thread(target=log_emitter, daemon=True).start()

def append_log(text: str, level: str = "info"):
    log_queue.put((text, level))
    logger.info(text)

def worker_status_callback(window_id: int, message: str):
    """Callback for browser workers."""
    level = "info"
    if "失败" in message or "error" in message.lower() or "崩溃" in message:
        level = "error"
    elif "warning" in message.lower() or "用尽" in message or "切换" in message:
        level = "warning"
    elif "保存" in message or "完成" in message:
        level = "success"
    log_queue.put((message, level))

# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/config", methods=["GET"])
def get_config():
    config.load()
    return jsonify(config.data)

@app.route("/api/config", methods=["POST"])
def save_config():
    data = request.json
    config.update(data)
    return jsonify({"status": "ok"})

@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    return jsonify(task_queue.get_all_tasks())

@app.route("/api/tasks", methods=["POST"])
def add_task():
    data = request.json
    prompt = data.get("prompt", "").strip()
    target_count = int(data.get("target_count", 1))
    if not prompt:
        return jsonify({"error": "Prompt cannot be empty"}), 400
    task = task_queue.add_task(prompt, target_count)
    # Broadcast task update
    socketio.emit("task_update", {"tasks": task_queue.get_all_tasks()})
    return jsonify(task)

@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    if task_queue.delete_task(task_id):
        socketio.emit("task_update", {"tasks": task_queue.get_all_tasks()})
        return jsonify({"status": "ok"})
    return jsonify({"error": "Task not found"}), 404

@app.route("/api/start", methods=["POST"])
def start_automation():
    global workers

    payload = request.json or {}
    wait_for_confirm = payload.get("wait_for_confirm", False)

    if workers and any(not w.is_stopped for w in workers):
        return jsonify({"error": "Already running"}), 400

    config.load()
    profile_dir = config.get("chrome_profile_base_dir")
    output_dir = config.get("output_dir")

    if not profile_dir or not os.path.isdir(profile_dir):
        return jsonify({"error": "Chrome 账号目录无效"}), 400
    if not output_dir:
        return jsonify({"error": "图片输出目录未设置"}), 400
    
    os.makedirs(output_dir, exist_ok=True)

    desired_windows = int(config.get("parallel_windows", 1))
    accounts_per_window_count = int(config.get("accounts_per_window", 10))

    # Generate the account names automatically
    accounts_per_window = []
    for i in range(1, desired_windows + 1):
        window_accounts = []
        for j in range(1, accounts_per_window_count + 1):
            acc_name = f"window_{i}_account_{j:02d}"
            window_accounts.append(acc_name)
            AccountManager.create_account_dir(profile_dir, acc_name)
        accounts_per_window.append(window_accounts)

    append_log("=" * 50)
    append_log(f"开始运行 — {desired_windows} 个窗口", "success")
    for i in range(desired_windows):
        append_log(f"  窗口 {i+1}: 分配 {len(accounts_per_window[i])} 个账号")
    append_log("=" * 50)

    workers = []
    for i in range(desired_windows):
        w = BrowserWorker(
            window_id=i + 1,
            profile_base_dir=profile_dir,
            account_names=accounts_per_window[i],
            task_queue=task_queue,
            output_dir=output_dir,
            image_prefix=config.get("image_name_prefix", "gemini_img"),
            config=config,
            status_callback=worker_status_callback,
            wait_for_confirm=wait_for_confirm,
        )
        workers.append(w)

    for w in workers:
        w.start()

    socketio.emit("status_update", {"status": "running" if not wait_for_confirm else "waiting"})

    # Monitor thread to wait for completion
    def _monitor():
        for w in workers:
            w.join()
        
        total_ok = sum(w.stats["completed"] for w in workers)
        total_fail = sum(w.stats["failed"] for w in workers)
        append_log(f"全部窗口已完成！成功: {total_ok}, 失败: {total_fail}", "success")
        
        socketio.emit("status_update", {"status": "stopped"})

    threading.Thread(target=_monitor, daemon=True).start()

    return jsonify({"status": "ok"})

@app.route("/api/confirm", methods=["POST"])
def confirm_automation():
    append_log("收到用户确认信号，准备开始自动化跑图...", "success")
    for w in workers:
        w.confirm_event.set()
    socketio.emit("status_update", {"status": "running"})
    return jsonify({"status": "ok"})

@app.route("/api/stop", methods=["POST"])
def stop_automation():
    append_log("正在停止所有窗口…", "warning")
    for w in workers:
        w.stop()
    return jsonify({"status": "ok"})

def run_app():
    logger.info("Starting Web UI on http://127.0.0.1:5050")
    
    import webbrowser
    def open_browser():
        time.sleep(1)
        webbrowser.open("http://127.0.0.1:5050")
    threading.Thread(target=open_browser, daemon=True).start()
    
    socketio.run(app, host="127.0.0.1", port=5050, allow_unsafe_werkzeug=True)
