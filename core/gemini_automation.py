"""Gemini web page automation — prompt input, image generation, and download."""

import time
import random
import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)

logger = logging.getLogger(__name__)

GEMINI_URL = "https://gemini.google.com/app"

# ---------------------------------------------------------------------------
# Selector strategies — ordered by likelihood.  We try each one until a
# visible, interactable element is found.
# ---------------------------------------------------------------------------

PROMPT_SELECTORS = [
    (By.CSS_SELECTOR, "rich-textarea .ql-editor"),
    (By.CSS_SELECTOR, "rich-textarea [contenteditable='true']"),
    (By.CSS_SELECTOR, ".text-input-field textarea"),
    (By.CSS_SELECTOR, "[aria-label*='prompt' i]"),
    (By.CSS_SELECTOR, "[aria-label*='Enter' i]"),
    (By.CSS_SELECTOR, "textarea"),
    (By.CSS_SELECTOR, "[contenteditable='true']"),
]

SEND_BUTTON_SELECTORS = [
    (By.CSS_SELECTOR, "button[aria-label*='Send' i]"),
    (By.CSS_SELECTOR, "button[aria-label*='发送' i]"),
    (By.CSS_SELECTOR, ".send-button"),
    (By.CSS_SELECTOR, "button.send-button"),
    (By.CSS_SELECTOR, "[data-mat-icon-name='send']"),
    (By.CSS_SELECTOR, "button[mat-icon-button] .send-icon"),
]

# Phrases that indicate the free quota has been exhausted.
QUOTA_INDICATORS = [
    "rate limit",
    "too many requests",
    "quota exceeded",
    "try again later",
    "usage limit",
    "请稍后再试",
    "达到限制",
    "已达到上限",
    "limit reached",
]

# CSS selectors for generated images (tried in order).
IMAGE_SELECTORS = [
    "img[src*='blob:']",
    ".response-container img",
    ".model-response img",
    "img[class*='generated']",
    "img[alt*='Generated']",
    ".image-container img",
    "img[src*='googleusercontent']",
    "img[src*='gstatic']",
    "img[src*='ggpht']",
]


class GeminiAutomation:
    """Drives the Gemini web UI to generate and download images."""

    def __init__(self, driver, generation_timeout=45):
        self.driver = driver
        self.wait = WebDriverWait(driver, 30)
        self.long_wait = WebDriverWait(driver, generation_timeout)
        self.generation_timeout = generation_timeout

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_gemini(self):
        """Open Gemini and wait for the page to become interactive.
        This blocks until the prompt input box is visible, giving the user 
        unlimited time to manually log in if necessary.
        """
        self.driver.get(GEMINI_URL)
        time.sleep(3)
        self.wait.until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        logger.info("正在等待加载或用户手动登录...")
        # Give the user up to 10 minutes to manually log in
        start_time = time.time()
        while time.time() - start_time < 600:
            try:
                # Quickly try to find the prompt box
                el = self._find_element_multi(PROMPT_SELECTORS, timeout=2)
                if el:
                    logger.info("检测到输入框，登录完成，准备自动化...")
                    break
            except NoSuchElementException:
                pass
            # Optional: check if driver was closed
            try:
                _ = self.driver.title
            except Exception:
                # Browser was closed manually
                break
            time.sleep(2)
            
        # Extra settle time for SPA hydration
        time.sleep(2)
        logger.info("Navigated to Gemini")

    def start_new_chat(self):
        """Start a fresh chat to avoid context carryover."""
        new_chat_selectors = [
            (By.CSS_SELECTOR, "button[aria-label*='New chat' i]"),
            (By.CSS_SELECTOR, "button[aria-label*='新对话' i]"),
            (By.CSS_SELECTOR, "button[aria-label*='新聊天' i]"),
            (By.CSS_SELECTOR, "a[href='/app']"),
        ]
        try:
            btn = self._find_element_multi(new_chat_selectors, timeout=5)
            btn.click()
            time.sleep(2)
        except (NoSuchElementException, TimeoutException):
            # Fallback: reload the page
            self.driver.get(GEMINI_URL)
            time.sleep(3)

    # ------------------------------------------------------------------
    # Prompt input & submission
    # ------------------------------------------------------------------

    def input_prompt(self, prompt_text: str):
        """Locate the prompt input and type *prompt_text* with human-like delays."""
        input_el = self._find_element_multi(PROMPT_SELECTORS)
        input_el.click()
        time.sleep(0.5)

        # Clear existing content
        try:
            input_el.clear()
        except WebDriverException:
            # contenteditable divs don't support .clear()
            input_el.send_keys(Keys.CONTROL + "a")
            input_el.send_keys(Keys.DELETE)
        time.sleep(0.3)

        # Type character-by-character for realism
        for ch in prompt_text:
            input_el.send_keys(ch)
            time.sleep(random.uniform(0.01, 0.06))

        time.sleep(0.5)
        logger.debug(f"Typed prompt ({len(prompt_text)} chars)")

    def upload_image(self, file_path: str):
        """Upload a local image file to Gemini."""
        import base64
        try:
            # First, try to find input[type='file'] piercing through shadow DOMs
            js_find_input = """
            function findFileInput(root) {
                if (root.matches && root.matches("input[type='file']")) return root;
                if (root.shadowRoot) {
                    let res = findFileInput(root.shadowRoot);
                    if (res) return res;
                }
                let children = root.children;
                if (children) {
                    for (let i = 0; i < children.length; i++) {
                        let res = findFileInput(children[i]);
                        if (res) return res;
                    }
                }
                return null;
            }
            return findFileInput(document.body);
            """
            file_input = self.driver.execute_script(js_find_input)
            
            if file_input:
                file_input.send_keys(file_path)
                logger.info(f"Uploaded reference image via file input: {file_path}")
                time.sleep(5)
                return
            else:
                logger.warning("No file input found in Shadow DOM. Falling back to JS Paste.")
                
        except Exception as e:
            logger.warning(f"File input strategy failed: {e}. Falling back to JS Paste.")
            
        # Fallback: dispatch a paste event with the image to the editor
        try:
            with open(file_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
                
            import os
            filename = os.path.basename(file_path) if file_path else "reference.jpg"
            js_paste = """
            var b64Data = arguments[0];
            var fileName = arguments[1];
            var promptEl = document.querySelector("rich-textarea .ql-editor") || 
                           document.querySelector("[contenteditable='true']") || 
                           document.querySelector("textarea") || 
                           document.activeElement;
            
            fetch("data:image/jpeg;base64," + b64Data)
            .then(res => res.blob())
            .then(blob => {
                var file = new File([blob], fileName, {type: "image/jpeg"});
                var dt = new DataTransfer();
                dt.items.add(file);
                var ev = new ClipboardEvent("paste", {
                    clipboardData: dt,
                    bubbles: true,
                    cancelable: true
                });
                promptEl.dispatchEvent(ev);
            });
            """
            self.driver.execute_script(js_paste, b64_data, filename)
            logger.info(f"Pasted reference image via JS: {file_path}")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Failed to upload reference image via paste: {e}")

    def submit_prompt(self):
        """Click the send button (or fall back to pressing Enter)."""
        try:
            send_btn = self._find_element_multi(SEND_BUTTON_SELECTORS, timeout=5)
            send_btn.click()
        except (NoSuchElementException, TimeoutException):
            logger.debug("Send button not found — pressing Enter instead")
            input_el = self._find_element_multi(PROMPT_SELECTORS, timeout=5)
            input_el.send_keys(Keys.RETURN)
        time.sleep(2)

    # ------------------------------------------------------------------
    # Waiting for generation
    # ------------------------------------------------------------------

    def wait_for_image_generation(self, existing_srcs=None):
        """Block until images appear, quota is exhausted, or we time out.

        Returns:
            'success' | 'quota_exhausted' | 'timeout'
        """
        start = time.time()
        while time.time() - start < self.generation_timeout:
            if self._check_quota_exhausted():
                return "quota_exhausted"
            if self._find_generated_images(existing_srcs=existing_srcs):
                return "success"
            time.sleep(3)
        return "timeout"

    # ------------------------------------------------------------------
    # Image discovery & download
    # ------------------------------------------------------------------

    def download_generated_images(self, existing_srcs=None):
        """Return a list of image payloads (base64 data-URIs, URLs, or raw bytes)."""
        images = self._find_generated_images(existing_srcs=existing_srcs)
        downloaded = []

        for idx, img_el in enumerate(images):
            try:
                data = self._extract_image_data(img_el)
                if data:
                    downloaded.append(data)
            except Exception as exc:
                logger.warning(f"Image {idx} extraction failed: {exc}")
                # Last resort: element screenshot
                try:
                    downloaded.append(img_el.screenshot_as_png)
                except Exception:
                    pass

        return downloaded

    # ------------------------------------------------------------------
    # High-level convenience
    # ------------------------------------------------------------------

    def _click_create_image_button(self):
        """Click the '+' button and select 'Create image' / '制作图片' using pure Selenium native clicks."""
        try:
            # 1. Find the '+' button
            plus_btn_xpath = "//button[contains(@aria-label, '上传') or contains(@aria-label, 'Upload') or contains(@aria-label, 'Add') or contains(@aria-label, '添加')]"
            try:
                plus_btn = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, plus_btn_xpath)))
                plus_btn.click()
            except TimeoutException:
                logger.warning("Could not find '+' button element via native Selenium.")
                return
            except Exception as e:
                logger.warning(f"Failed to click '+' button: {e}")
                return

            # Wait for menu animation
            time.sleep(1.0)
            
            # 2. Find the menu item
            menu_item_xpath = "//*[(contains(text(), '制作图片') or contains(text(), 'Create image') or contains(text(), 'Imagen')) and not(self::script) and not(self::style)]"
            try:
                elements = self.driver.find_elements(By.XPATH, menu_item_xpath)
                clicked = False
                for el in elements:
                    if el.is_displayed():
                        # Make sure it's not a huge chat bubble
                        if len(el.text.strip()) > 30:
                            continue
                        try:
                            el.click()
                            clicked = True
                            logger.info("Successfully clicked 'Create image' / '制作图片' button natively.")
                            break
                        except Exception:
                            # Fallback if native click fails due to overlap
                            self.driver.execute_script("arguments[0].click();", el)
                            clicked = True
                            logger.info("Successfully clicked 'Create image' via JS fallback on native element.")
                            break
                
                if not clicked:
                    logger.warning("Found 'Create image' text, but could not click it.")
                    try:
                        self.driver.execute_script("document.body.click();")
                    except:
                        pass
                else:
                    time.sleep(1.0)
            except Exception as e:
                logger.warning(f"Error finding menu item: {e}")
                
        except Exception as e:
            logger.warning(f"Error in _click_create_image_button: {e}")

    def generate_and_download(self, prompt_text: str, reference_image_paths: list = None):
        """Full flow: type prompt → (optional) upload images → submit → wait → download."""
        logger.info(f"Generating: {prompt_text[:60]}…")

        self._click_create_image_button()
        self.input_prompt(prompt_text)
        
        if reference_image_paths:
            import os
            for ref_path in reference_image_paths:
                abs_path = os.path.abspath(ref_path)
                if os.path.exists(abs_path):
                    self.upload_image(abs_path)
                else:
                    logger.error(f"Reference image not found: {abs_path}")

        # Capture all existing image srcs BEFORE clicking submit
        # This ensures we don't accidentally download the reference image later
        existing_srcs = set()
        try:
            for img in self.driver.find_elements(By.TAG_NAME, "img"):
                src = img.get_attribute("src")
                if src:
                    existing_srcs.add(src)
        except Exception:
            pass

        self.submit_prompt()

        status = self.wait_for_image_generation(existing_srcs=existing_srcs)

        if status != "success":
            logger.warning(f"Generation status: {status}")
            return None, status

        # Let images fully render
        time.sleep(3)

        images = self.download_generated_images(existing_srcs=existing_srcs)
        if images:
            logger.info(f"Downloaded {len(images)} image(s)")
            return images, "success"

        return None, "no_images"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_element_multi(self, selectors, timeout=15):
        """Try *selectors* one by one; return the first visible element found."""
        last_exc = None
        for by, sel in selectors:
            try:
                el = WebDriverWait(self.driver, min(timeout, 3)).until(
                    EC.presence_of_element_located((by, sel))
                )
                if el.is_displayed():
                    return el
            except (TimeoutException, NoSuchElementException,
                    StaleElementReferenceException) as exc:
                last_exc = exc
        raise NoSuchElementException(
            f"None of {len(selectors)} selectors matched a visible element"
        ) from last_exc

    def _check_quota_exhausted(self):
        """Return True if the page contains a quota-exhaustion message."""
        try:
            text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            return any(ind in text for ind in QUOTA_INDICATORS)
        except Exception:
            return False

    def _find_generated_images(self, existing_srcs=None):
        """Return a de-duplicated list of <img> WebElements that look like
        generated images (ignoring tiny icons and SVGs).
        """
        if existing_srcs is None:
            existing_srcs = set()
            
        seen_srcs = set()
        results = []

        for sel in IMAGE_SELECTORS:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for img in elements:
                    src = img.get_attribute("src") or ""
                    if src in seen_srcs or src.startswith("data:image/svg"):
                        continue
                    
                    # CRITICAL FIX: Skip images that were already on the page before generation
                    # (e.g. the reference image we just uploaded)
                    if src in existing_srcs:
                        continue

                    alt = (img.get_attribute("alt") or "").lower()
                    # Filter out profile pictures explicitly
                    if "google account" in alt or "profile" in alt or "头像" in alt or "avatar" in alt:
                        continue

                    # Use rendered size to filter out UI icons (like the 32x32 avatar)
                    try:
                        size = img.size
                        w = size.get('width', 0)
                        h = size.get('height', 0)
                    except Exception:
                        w, h = 0, 0
                        
                    if w > 100 and h > 100:
                        seen_srcs.add(src)
                        results.append(img)
            except (StaleElementReferenceException, WebDriverException):
                continue

        return results

    def _extract_image_data(self, img_element):
        """Try to get usable image bytes from an <img> element.

        Strategy:
          1. Canvas toDataURL (works for same-origin / CORS-enabled)
          2. Fetch the ``src`` URL via requests
        """
        # Strategy 1: JavaScript canvas
        try:
            data_url = self.driver.execute_script(
                """
                var img = arguments[0];
                var c = document.createElement('canvas');
                c.width  = img.naturalWidth  || img.width;
                c.height = img.naturalHeight || img.height;
                var ctx = c.getContext('2d');
                ctx.drawImage(img, 0, 0);
                try { return c.toDataURL('image/jpeg', 0.95); }
                catch(e) { return null; }
                """,
                img_element,
            )
            if data_url and data_url.startswith("data:"):
                return data_url
        except WebDriverException:
            pass

        # Strategy 2: plain URL
        src = img_element.get_attribute("src")
        if src and src.startswith("http"):
            return src

        return None
