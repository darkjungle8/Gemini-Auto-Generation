"""BrowserWorker — one thread per parallel browser window.

Each worker:
  1. Launches Chrome with its first assigned account (user-data-dir).
  2. Reads prompts from its Excel sheet.
  3. For each prompt, generates an image via GeminiAutomation.
  4. Downloads and saves the image as JPG.
  5. Marks the prompt row in Excel.
  6. On quota exhaustion, closes Chrome and re-opens with the next account.
"""

import os
import time
import queue
import random
import logging
import threading

import undetected_chromedriver as uc

from core.gemini_automation import GeminiAutomation
from core.account_manager import AccountManager
from core.image_downloader import ImageDownloader

logger = logging.getLogger(__name__)


class BrowserWorker(threading.Thread):
    """Autonomous worker that drives one Chrome window."""

    def __init__(
        self,
        window_id: int,
        profile_base_dir: str,
        account_names: list,
        task_queue,
        output_dir: str,
        image_prefix: str,
        config,
        status_callback=None,
        image_counter_start: int = 0,
        wait_for_confirm: bool = False,
    ):
        super().__init__(daemon=True, name=f"Worker-{window_id}")
        self.window_id = window_id
        self.profile_base_dir = profile_base_dir
        self.account_mgr = AccountManager(profile_base_dir, account_names)
        self.task_queue = task_queue
        self.output_dir = output_dir
        self.image_prefix = image_prefix
        self.config = config
        self.status_callback = status_callback
        self.mine_request_queue = queue.Queue()

        self.driver = None
        self.automation = None
        self._stop_event = threading.Event()
        self.confirm_event = threading.Event()
        if not wait_for_confirm:
            self.confirm_event.set()

        # Thread-safe image counter
        self._img_counter_lock = threading.Lock()
        self._img_counter = image_counter_start

        self.stats = {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "current_account": "",
        }

    # ------------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------------

    def _log(self, message, level="info"):
        full = f"[窗口 {self.window_id}] {message}"
        getattr(logger, level)(full)
        if self.status_callback:
            self.status_callback(self.window_id, full)

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    def _create_driver(self) -> bool:
        user_data_dir = self.account_mgr.get_current_user_data_dir()
        if not user_data_dir:
            self._log("没有可用的账号！", "error")
            return False

        account = self.account_mgr.get_current_account()
        self.stats["current_account"] = account
        self._log(f"正在启动浏览器，账号: {account}")

        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-popup-blocking")
        # Suppress infobar "Chrome is being controlled by automated test software"
        options.add_argument("--disable-infobars")

        try:
            self.driver = uc.Chrome(options=options)
            self.driver.set_window_size(1280, 900)
            self.automation = GeminiAutomation(self.driver)
            return True
        except Exception as exc:
            self._log(f"浏览器启动失败: {exc}", "error")
            return False

    def _close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            self.automation = None

    def _switch_account(self) -> bool:
        """Close current browser, open a new one with the next account."""
        self._log("正在切换到下一个账号…")
        self._close_driver()
        time.sleep(2)

        if self.account_mgr.switch_to_next():
            return self._create_driver()
        self._log("所有账号均已用尽！", "warning")
        return False

    # ------------------------------------------------------------------
    # Image counter
    # ------------------------------------------------------------------

    def _next_image_number(self) -> int:
        with self._img_counter_lock:
            self._img_counter += 1
            return self._img_counter

    # ------------------------------------------------------------------
    # Main thread entry
    # ------------------------------------------------------------------

    def run(self):
        try:
            self._run_loop()
        except Exception as exc:
            self._log(f"工作线程崩溃: {exc}", "error")
        finally:
            self._close_driver()
            self._log(
                f"已停止 — 完成: {self.stats['completed']}, "
                f"失败: {self.stats['failed']}"
            )

    def _check_and_run_mining(self):
        while not self.mine_request_queue.empty():
            req = self.mine_request_queue.get()
            self._log("[挖掘机] 收到亚马逊挖掘请求，正在新标签页中执行...")
            try:
                original_window = self.driver.current_window_handle
                self.driver.execute_script("window.open('about:blank', '_blank');")
                new_window = [w for w in self.driver.window_handles if w != original_window][-1]
                self.driver.switch_to.window(new_window)
                
                from core.amazon_miner import AmazonMiner
                miner = AmazonMiner(driver=self.driver)
                prompts = miner.mine_trends(req["keyword"], req["limit"])
                
                if not prompts:
                    self._log("[挖掘机] ❌ 未找到符合条件的商品（可能被 CAPTCHA 拦截或商品都是大套装）", "error")
                else:
                    self._log(f"[挖掘机] ✅ 挖掘完成！共获得 {len(prompts)} 个生图任务", "info")
                    for item_dict in prompts:
                        self.task_queue.add_task(
                            prompt=item_dict["prompt"], 
                            target_count=req["target_count"], 
                            reference_image_path=item_dict.get("reference_image_path")
                        )
                
                self.driver.close()
                self.driver.switch_to.window(original_window)
            except Exception as e:
                self._log(f"[挖掘机] ❌ 挖掘失败: {e}", "error")
                try:
                    if len(self.driver.window_handles) > 0:
                        self.driver.switch_to.window(self.driver.window_handles[0])
                except:
                    pass

    def _run_loop(self):
        if not self._create_driver():
            return

        self.automation.navigate_to_gemini()
        
        if not self.confirm_event.is_set():
            self._log("等待手动登录 Gemini... 此时您也可以开新标签页登录 Amazon 或者直接挖掘")
            while not self._stop_event.is_set() and not self.confirm_event.is_set():
                self._check_and_run_mining()
                time.sleep(1)
            
            if self._stop_event.is_set():
                return
            self._log("收到确认信号，准备开始自动化跑图！")
        
        self._log("已进入自动跑图模式")

        retry_limit = self.config.get("retry_count", 3)
        cooldown = int(self.config.get("cooldown_time", 3))

        while not self._stop_event.is_set():
            self._check_and_run_mining()
            
            task = self.task_queue.get_next_task()
            if not task:
                time.sleep(3)
                continue
                
            self._log(f"领到任务 [{task['id']}]: {task['prompt'][:20]}... 目标 {task['target_count']} 张")

            while task["current_count"] < task["target_count"] and not self._stop_event.is_set():
                success, images_saved = self._process_task_generation(task, retry_limit)
                
                if success and images_saved > 0:
                    task = self.task_queue.update_task_progress(task["id"], images_saved)
                    if not task: # task might be deleted
                        break
                    
                    self.stats["completed"] += images_saved
                    self._log(f"任务 [{task['id']}] 进度: {task['current_count']} / {task['target_count']}")
                    
                    if task["current_count"] >= task["target_count"]:
                        self._log(f"任务 [{task['id']}] 已完成！")
                        break
                    
                    # Cooldown before generating more for the same task
                    if not self._stop_event.is_set():
                        self._log(f"等待 {cooldown} 秒后进行下一次生成...")
                        time.sleep(cooldown)
                        self._log("正在开启新对话...")
                        self.automation.start_new_chat()
                        self._log("新对话开启完毕，准备生成下一张！")
                elif not success:
                    self.stats["failed"] += 1
                    self.task_queue.mark_failed(task["id"], "生成失败")
                    self._log(f"任务 [{task['id']}] 生成失败，已终止。")
                    break

            # Start a new chat for the next task
            if not self._stop_event.is_set():
                self.automation.start_new_chat()

    # ------------------------------------------------------------------
    # Single prompt processing
    # ------------------------------------------------------------------

    def _process_task_generation(self, task, retry_limit: int):
        prompt = task["prompt"]
        for attempt in range(1, retry_limit + 1):
            if self._stop_event.is_set():
                return False, 0

            self._log(f"执行生成 (第 {attempt} 次尝试)...")

            try:
                images, status = self.automation.generate_and_download(
                    prompt, 
                    reference_image_path=task.get("reference_image_path")
                )

                if status == "quota_exhausted":
                    self._log("免费额度已用尽，切换账号中…")
                    if not self._switch_account():
                        self._log("所有账号额度均已用尽，停止工作")
                        self._stop_event.set()
                        return False, 0
                    self.automation.navigate_to_gemini()
                    continue  # retry with new account

                if status == "success" and images:
                    saved_files = self._save_images(images)
                    return True, len(saved_files)

                # timeout / no_images → retry
                self._log(f"生成失败 ({status})，准备重试…")
                self.automation.start_new_chat()
                time.sleep(2)

            except Exception as exc:
                self._log(f"异常: {exc}", "error")
                time.sleep(3)

        return False, 0

    # ------------------------------------------------------------------
    # Save downloaded images
    # ------------------------------------------------------------------

    def _save_images(self, image_data_list: list) -> list:
        saved_files = []
        for img_data in image_data_list:
            num = self._next_image_number()
            filename = f"{self.image_prefix}_{num:04d}.jpg"
            filepath = os.path.join(self.output_dir, filename)
            try:
                ImageDownloader.download_and_save_as_jpg(img_data, filepath)
                saved_files.append(filename)
                self._log(f"已保存: {filename}")
            except Exception as exc:
                self._log(f"图片保存失败: {exc}", "warning")
        return saved_files

    # ------------------------------------------------------------------
    # External control
    # ------------------------------------------------------------------

    def stop(self):
        """Request the worker to stop gracefully after the current prompt."""
        self._stop_event.set()

    @property
    def is_stopped(self):
        return self._stop_event.is_set()
