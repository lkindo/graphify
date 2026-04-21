import os
from pypdf import PdfReader
import json
import re

PDF_PATH = r"d:/project/graphify/pdf/koreantree.pdf"
OUT_DIR = r"d:/project/graphify/assets/species"
HTML_PATH = r"d:/project/graphify/encyclopedia_mockup.html"

reader = PdfReader(PDF_PATH)
found_p = None

# 1. Search for Thymus (섬백리향) in body pages (ignoring TOC)
print("Locating Thymus (섬백리향)...")
for i in range(10, 50): # Search early body pages
    try:
        text = reader.pages[i].extract_text()
        if "Thymus" in text:
            found_p = i
            print(f"Found on physical page {i}")
            break
    except: continue

if found_p is not None:
    # 2. Extract 2 images
    imgs = sorted([img.data for img in reader.pages[found_p].images if len(img.data) > 10000], key=len, reverse=True)
    # Also check next page just in case
    next_imgs = sorted([img.data for img in reader.pages[found_p+1].images if len(img.data) > 10000], key=len, reverse=True)
    
    final_imgs = []
    if imgs: final_imgs.append(imgs[0])
    if next_imgs: final_imgs.append(next_imgs[0])
    
    paths = []
    for idx, data in enumerate(final_imgs[:2]):
        fname = f"섬백리향_{idx+1}.png"
        with open(os.path.join(OUT_DIR, fname), "wb") as f:
            f.write(data)
        paths.append(f"assets/species/{fname}")
    
    # 3. Update HTML JSON
    with open(HTML_PATH, 'r', encoding='utf-8') as f:
        html = f.read()
    
    data_match = re.search(r'<script id="botanicalData" type="application/json">(.*?)</script>', html, flags=re.DOTALL)
    if data_match:
        data = json.loads(data_match.group(1))
        found_entry = False
        for sp in data["species"]:
            if "섬백리향" in sp["name"] or "미꽃차례" in sp["name"]:
                sp["name"] = "섬백리향"
                sp["scientific_name"] = "Thymus quinquecostatus"
                sp["images"] = paths
                found_entry = True
                break
        
        if found_entry:
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            new_html = re.sub(r'<script id="botanicalData" type="application/json">.*?</script>',
                             f'<script id="botanicalData" type="application/json">{json_str}</script>',
                             html, flags=re.DOTALL)
            with open(HTML_PATH, 'w', encoding='utf-8') as f:
                f.write(new_html)
            print("Successfully updated 섬백리향 with 2 images.")
        else:
            print("Could not find the entry to update.")
