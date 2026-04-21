import os
import json
import re

HTML_PATH = r"d:/project/graphify/encyclopedia_mockup.html"
IMG_DIR = r"d:/project/graphify/assets/species"

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update text in JSON
new_html = html.replace("광랄", "광귤")

# 2. Rename physical files if they exist
for f in os.listdir(IMG_DIR):
    if "광랄" in f:
        old_path = os.path.join(IMG_DIR, f)
        new_f = f.replace("광랄", "광귤")
        new_path = os.path.join(IMG_DIR, new_f)
        try:
            os.rename(old_path, new_path)
            print(f"Renamed: {f} -> {new_f}")
        except: pass

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(new_html)

print("광귤 typo corrected across database and assets.")
