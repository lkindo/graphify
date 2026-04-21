import os
import json
import re
from pypdf import PdfReader

HTML_PATH = r"d:/project/graphify/encyclopedia_mockup.html"
PDF_PATH = r"d:/project/graphify/pdf/koreantree.pdf"
OUT_DIR = r"d:/project/graphify/assets/species"

reader = PdfReader(PDF_PATH)

# TARGET: 백리향 (p14, p15)
p14_idx = 13
p15_idx = 14

print("Adding 백리향 using pages 14 & 15...")

paths = []
# Image from p14
imgs14 = sorted([img.data for img in reader.pages[p14_idx].images if len(img.data) > 15000], key=len, reverse=True)
if imgs14:
    with open(os.path.join(OUT_DIR, "백리향_1.png"), "wb") as f: f.write(imgs14[0])
    paths.append("assets/species/백리향_1.png")

# Image from p15
imgs15 = sorted([img.data for img in reader.pages[p15_idx].images if len(img.data) > 15000], key=len, reverse=True)
if imgs15:
    with open(os.path.join(OUT_DIR, "백리향_2.png"), "wb") as f: f.write(imgs15[0])
    paths.append("assets/species/백리향_2.png")

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

data_match = re.search(r'<script id="botanicalData" type="application/json">(.*?)</script>', html, flags=re.DOTALL)
if data_match:
    data = json.loads(data_match.group(1))
    
    # Check if 백리향 exists or find insertion point after 섬백리향
    found = False
    for sp in data["species"]:
        if "백리향" == sp["name"]:
            sp["images"] = paths
            found = True
            break
    
    if not found:
        # Find 섬백리향 and insert after it
        idx_to_insert = 0
        for i, sp in enumerate(data["species"]):
            if "섬백리향" in sp["name"]:
                idx_to_insert = i + 1
                break
        
        data["species"].insert(idx_to_insert, {
            "name": "백리향",
            "scientific_name": "Thymus quinquecostatus var. japonica",
            "family": "꿀풀과",
            "images": paths,
            "summary": "향기가 백 리를 간다고 하여 백리향이라 불리며, 섬백리향보다 잎과 꽃이 다소 작고 섬세한 특징이 있습니다. (도감 14-15쪽)",
            "details": {"분류": "꿀풀과", "학명": "Thymus quinquecostatus var. japonica", "특징": "바위 곁이나 건조한 산지에서 자라는 상록 반관목"}
        })

    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    new_html = re.sub(r'<script id="botanicalData" type="application/json">.*?</script>',
                     f'<script id="botanicalData" type="application/json">{json_str}</script>',
                     html, flags=re.DOTALL)
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(new_html)

print("백리향 Addition Complete.")
