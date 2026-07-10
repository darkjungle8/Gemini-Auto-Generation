import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

options = uc.ChromeOptions()
# Not headless so it doesn't crash on Mac
# options.add_argument("--headless")
driver = uc.Chrome(options=options)
driver.get("https://gemini.google.com/app")
print("Waiting for page load (20s)... please log in manually if needed.")
time.sleep(20)

buttons = driver.find_elements(By.TAG_NAME, "button")
for b in buttons:
    aria = b.get_attribute("aria-label")
    if aria and ("upload" in aria.lower() or "上传" in aria):
        print("Found upload button:", aria, b.get_attribute("outerHTML")[:100])
        b.click()
        print("Clicked!")
        time.sleep(2)
        break

try:
    file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
    print("Found file input:", file_input.get_attribute("outerHTML"))
except Exception as e:
    print("No file input found:", type(e).__name__)

driver.quit()
