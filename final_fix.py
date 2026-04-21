import os
import json
import re
from pypdf import PdfReader

HTML_PATH = r"d:/project/graphify/encyclopedia_mockup.html"
PDF_PATH = r"d:/project/graphify/pdf/koreantree.pdf"
OUT_DIR = r"d:/project/graphify/assets/species"

reader = PdfReader(PDF_PATH)

# Extract images for 섬백리향 from around page 17-18 (where it actually is in content)
# We find the images and save them properly
# Page 17/18 in PDF usually corresponds to start of content
target_page = 17 # Heuristic match
imgs = sorted([img.data for img in reader.pages[target_page].images if len(img.data) > 15000], key=len, reverse=True)
next_imgs = sorted([img.data for img in reader.pages[target_page+1].images if len(img.data) > 15000], key=len, reverse=True)

paths = []
if imgs:
    with open(os.path.join(OUT_DIR, "섬백리향_1.png"), "wb") as f: f.write(imgs[0])
    paths.append("assets/species/섬백리향_1.png")
if next_imgs:
    with open(os.path.join(OUT_DIR, "섬백리향_2.png"), "wb") as f: f.write(next_imgs[0])
    paths.append("assets/species/섬백리향_2.png")

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

data_match = re.search(r'<script id="botanicalData" type="application/json">(.*?)</script>', html, flags=re.DOTALL)
if data_match:
    data = json.loads(data_match.group(1))
    
    # Correct the specific entry
    for sp in data["species"]:
        if "섬백리향" in sp["name"] or "미꽃차례" in sp["name"]:
            sp["name"] = "섬백리향"
            sp["scientific_name"] = "Thymus quinquecostatus"
            sp["images"] = paths
            sp["summary"] = "울릉도에서 자생하는 꿀풀과의 반관목으로 향기가 강하며 지표면을 덮는 특징이 있습니다."
            break
            
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    new_html = re.sub(r'<script id="botanicalData" type="application/json">.*?</script>',
                     f'<script id="botanicalData" type="application/json">{json_str}</script>',
                     html, flags=re.DOTALL)
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print("Done.")
