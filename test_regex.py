import re
url = "https://m.media-amazon.com/images/I/81abc._AC_SR38,50_.jpg"
print(re.sub(r'\._.*?_\.', '.', url))

url2 = "https://m.media-amazon.com/images/I/81+X1hU._AC_SL1500_.jpg"
print(re.sub(r'\._.*?_\.', '.', url2))
