import os
import re
import json

HTML_PATH = r"d:/project/graphify/encyclopedia_mockup.html"
IMG_DIR = r"d:/project/graphify/assets/species"

print("Starting asset cleanup...")

# 1. Get used image list from HTML
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

json_match = re.search(r'<script id="botanicalData" type="application/json">(.*?)</script>', content, flags=re.DOTALL)
if not json_match:
    print("Error: Could not find botanicalData in HTML.")
    exit(1)

data = json.loads(json_match.group(1))
used_images = set()

for sp in data.get("species", []):
    for img_path in sp.get("images", []):
        # Path is usually 'assets/species/Name_1.png'
        filename = os.path.basename(img_path)
        used_images.add(filename.lower())

print(f"Used images detected: {len(used_images)}")

# 2. Scan directory and delete unused
deleted_count = 0
if not os.path.exists(IMG_DIR):
    print("Image directory does not exist.")
    exit(1)

for f in os.listdir(IMG_DIR):
    f_path = os.path.join(IMG_DIR, f)
    if os.path.isfile(f_path):
        if f.lower() not in used_images:
            try:
                os.remove(f_path)
                deleted_count += 1
            except:
                print(f"Failed to delete {f}")

print(f"Cleanup finished. Deleted {deleted_count} unnecessary image files.")
