import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time

def test_amazon():
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    driver.get("https://www.amazon.com/s?k=ditsy+floral+fabric&s=exact-aware-popularity-rank")
    time.sleep(5)
    print("Title:", driver.title)
    items = driver.find_elements(By.CSS_SELECTOR, "[data-component-type='s-search-result']")
    print(f"Found {len(items)} items")
    for item in items[:3]:
        try:
            title = item.find_element(By.CSS_SELECTOR, "h2 a span").text
            img = item.find_element(By.CSS_SELECTOR, ".s-image").get_attribute("src")
            print("-", title)
            print("  Img:", img)
        except Exception as e:
            print("Error parsing item:", e)
    driver.quit()

test_amazon()
