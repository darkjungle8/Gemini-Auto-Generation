import os
import re
import time
import logging
import requests
import uuid

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from core.pattern_analyzer import get_dominant_color_from_local, is_collage
from core.prompt_generator import generate_prompts

logger = logging.getLogger(__name__)


class AmazonMiner:
    def __init__(self, driver=None):
        self.driver = driver

    def _is_valid_product(self, title_text):
        """Filter out products with >=10 pieces. Keep 1pc, 4pc, 6pc etc."""
        t = title_text.lower()
        matches = re.findall(r'(\d+)\s*(?:pc|pcs|piece|pieces|square|squares|sheet|sheets)\b', t)
        for m in matches:
            if int(m) >= 10:
                return False
        return True

    def _get_all_high_res_images(self, driver):
        """Extract all unique high-res product images from a detail page (main + thumbnails)."""
        image_urls = []
        
        # Look for thumbnails and main images
        selectors = [
            (By.CSS_SELECTOR, "#altImages img"),
            (By.CSS_SELECTOR, "#imageBlock img"),
            (By.ID, "landingImage"),
        ]
        
        for by, sel in selectors:
            try:
                elements = driver.find_elements(by, sel)
                for img_el in elements:
                    # Prefer data-old-hires if available
                    hi_res = img_el.get_attribute("data-old-hires")
                    src = img_el.get_attribute("src")
                    
                    target_url = hi_res if (hi_res and hi_res.startswith("http")) else src
                    if target_url and target_url.startswith("http"):
                        # Strip Amazon's thumbnail modifiers (e.g., ._AC_SR38,50_.jpg -> .jpg)
                        import re
                        clean_url = re.sub(r'\._.*?_\.', '.', target_url)
                        
                        # Filter out tiny icon images, videos, and UI elements
                        if "transparent-pixel" not in clean_url and "play-button" not in clean_url and "icon" not in clean_url:
                            if clean_url not in image_urls:
                                image_urls.append(clean_url)
            except:
                continue
                
        # Limit to 6 images maximum per product to avoid scraping too much garbage
        return image_urls[:6]

    def mine_trends(self, keyword="ditsy floral fabric", limit=5):
        logger.info(f"Starting Amazon Miner for keyword: {keyword}, limit: {limit}")
        
        we_created_driver = False
        driver = self.driver
        if not driver:
            options = uc.ChromeOptions()
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument("--disable-popup-blocking")
            driver = uc.Chrome(options=options)
            we_created_driver = True
        
        results = []
        try:
            # Search with popularity sort
            url = f"https://www.amazon.com/s?k={keyword.replace(' ', '+')}&s=exact-aware-popularity-rank"
            driver.get(url)
            time.sleep(5)
            
            # Handle CAPTCHA
            if "captcha" in driver.current_url.lower() or "Type the characters" in driver.page_source:
                logger.warning("Amazon CAPTCHA detected. Please solve it manually...")
                time.sleep(20)
            
            # Find search results
            items = driver.find_elements(By.CSS_SELECTOR, "[data-component-type='s-search-result']")
            if not items:
                logger.error("No search results found.")
                return []
                
            logger.info(f"Found {len(items)} items on page. Filtering and collecting top {limit}...")
            
            # Collect detail links with titles (filter in the list page)
            detail_links = []
            for item in items:
                if len(detail_links) >= limit:
                    break
                try:
                    title_el = item.find_element(By.CSS_SELECTOR, "h2")
                    title_text = title_el.text.strip()
                    
                    if not title_text:
                        continue
                    
                    # The user explicitly wants to SKIP products that are bundles or multi-piece sets
                    # because their images always have folds/overlaps that ruin the AI's structural generation.
                    title_lower = title_text.lower()
                    bundle_keywords = ["pcs", "pieces", "pack", "fat quarter", "bundle", "assortment", "set", "squares", "rolls", "strips", "jelly roll", "charm pack"]
                    if any(kw in title_lower for kw in bundle_keywords):
                        logger.info(f"Skipping bundle/multi-piece product: {title_text[:40]}...")
                        continue
                    
                    # Find link
                    try:
                        link_el = item.find_element(By.CSS_SELECTOR, "a.a-link-normal")
                        detail_url = link_el.get_attribute("href")
                    except:
                        detail_url = ""
                    
                    if detail_url:
                        detail_links.append({"url": detail_url, "list_title": title_text})
                        logger.info(f"Selected: {title_text[:60]}...")
                except:
                    continue
                    
            if not detail_links:
                logger.error("No valid products found after filtering.")
                return []
            
            logger.info(f"Collected {len(detail_links)} products. Now visiting detail pages...")
            
            os.makedirs("downloads/references", exist_ok=True)
            
            # Visit each detail page
            for idx, item_info in enumerate(detail_links):
                try:
                    logger.info(f"[{idx+1}/{len(detail_links)}] Opening detail page...")
                    driver.get(item_info["url"])
                    time.sleep(4)
                    
                    # Get product title from detail page
                    try:
                        title = driver.find_element(By.ID, "productTitle").text.strip()
                    except:
                        title = item_info["list_title"]
                    
                    # For 1-piece sets, we only need the MAIN image. 
                    # Other thumbnail images might contain text, people, or size charts which trigger Gemini's safety filters!
                    img_urls = self._get_all_high_res_images(driver)
                    
                    if not img_urls:
                        logger.warning(f"No image found for: {title[:50]}...")
                        continue
                        
                    img_urls = img_urls[:1] # ONLY KEEP THE MAIN IMAGE
                    logger.info(f"Using main image only for 1-piece product to avoid AI safety filters.")
                    
                    for img_idx, img_url in enumerate(img_urls):
                        try:
                            # Download image
                            resp = requests.get(img_url, timeout=15, headers={
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                            })
                            if resp.status_code != 200:
                                logger.warning(f"Image download failed (HTTP {resp.status_code})")
                                continue
                                
                            local_filename = f"downloads/references/{uuid.uuid4().hex[:8]}.jpg"
                            local_path = os.path.abspath(local_filename)
                            with open(local_path, "wb") as f:
                                f.write(resp.content)
                                
                            logger.info(f"Downloaded reference image {img_idx+1}: {local_path}")
                            
                            # Extract dominant color
                            bg_color = get_dominant_color_from_local(local_path)
                            
                            # Generate prompts
                            prompts = generate_prompts(title, bg_color)
                            
                            for p in prompts:
                                results.append({
                                    "prompt": p,
                                    "reference_image_path": local_path
                                })
                        except Exception as inner_e:
                            logger.error(f"Error processing image {img_idx+1}: {inner_e}")
                            continue
                        
                except Exception as e:
                    logger.error(f"Error on detail page: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Miner error: {e}")
        finally:
            if we_created_driver:
                try:
                    driver.quit()
                except:
                    pass
            
        logger.info(f"Miner finished. Generated {len(results)} prompt tasks.")
        return results
