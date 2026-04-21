import os
import json
import re
from pypdf import PdfReader

HTML_PATH = r"d:/project/graphify/encyclopedia_mockup.html"
PDF_PATH = r"d:/project/graphify/pdf/koreantree.pdf"
OUT_DIR = r"d:/project/graphify/assets/species"

reader = PdfReader(PDF_PATH)

# TARGET: 섬백리향 (p12, p13)
p12_idx = 11
p13_idx = 12

print("Fixing 섬백리향 using pages 12 & 13...")

paths = []
# Image from p12
imgs12 = sorted([img.data for img in reader.pages[p12_idx].images if len(img.data) > 15000], key=len, reverse=True)
if imgs12:
    with open(os.path.join(OUT_DIR, "섬백리향_1.png"), "wb") as f: f.write(imgs12[0])
    paths.append("assets/species/섬백리향_1.png")

# Image from p13
imgs13 = sorted([img.data for img in reader.pages[p13_idx].images if len(img.data) > 15000], key=len, reverse=True)
if imgs13:
    with open(os.path.join(OUT_DIR, "섬백리향_2.png"), "wb") as f: f.write(imgs13[0])
    paths.append("assets/species/섬백리향_2.png")

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

data_match = re.search(r'<script id="botanicalData" type="application/json">(.*?)</script>', html, flags=re.DOTALL)
if data_match:
    data = json.loads(data_match.group(1))
    
    # 1. Update or Add 섬백리향
    found = False
    for sp in data["species"]:
        if "섬백리향" in sp["name"] or "미꽃차례" in sp["name"] or "섬백리항" in sp["name"]:
            sp["name"] = "섬백리향"
            sp["scientific_name"] = "Thymus quinquecostatus"
            sp["images"] = paths
            sp["summary"] = "울릉도에서 자생하는 우리나라 고유종으로 향기가 십 리까지 간다고 하여 섬백리향이라 부릅니다. (도감 12-13쪽)"
            found = True
            break
    
    if not found:
        data["species"].insert(0, {
            "name": "섬백리향",
            "scientific_name": "Thymus quinquecostatus",
            "family": "꿀풀과",
            "images": paths,
            "summary": "울릉도에서 자생하는 우리나라 고유종으로 향기가 십 리까지 간다고 하여 섬백리향이라 부릅니다. (도감 12-13쪽)",
            "details": {"분류": "꿀풀과", "학명": "Thymus quinquecostatus", "특징": "꽃이 줄기 끝에 모여 피며 향이 매우 강함"}
        })

    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    new_html = re.sub(r'<script id="botanicalData" type="application/json">.*?</script>',
                     f'<script id="botanicalData" type="application/json">{json_str}</script>',
                     html, flags=re.DOTALL)
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(new_html)

print("섬백리향 Restoration Complete.")
