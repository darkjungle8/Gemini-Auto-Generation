import requests
import os

os.makedirs("downloads/references", exist_ok=True)
url = "https://m.media-amazon.com/images/I/71Y-1-2-3L._AC_SX679_.jpg" # fake url
try:
    resp = requests.get(url, timeout=10)
    if resp.status_code == 200:
        with open("downloads/references/test.jpg", "wb") as f:
            f.write(resp.content)
        print("Success")
except Exception as e:
    print(e)
