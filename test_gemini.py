import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

options = uc.ChromeOptions()
options.add_argument("--headless")
driver = uc.Chrome(options=options)
driver.get("https://gemini.google.com/app")
time.sleep(10)
try:
    file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
    print("Found file input:", file_input.get_attribute("outerHTML"))
except Exception as e:
    print("No file input found:", type(e).__name__)
driver.quit()
