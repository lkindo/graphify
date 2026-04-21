import os
import re
import json
import shutil
from pypdf import PdfReader

# Configuration
PDF_PATH = r"d:/project/graphify/pdf/koreantree.pdf"
TOC_PATH = r"d:/project/graphify/full_toc_text.txt"
OUTPUT_DIR = r"d:/project/graphify/assets/species"
HTML_PATH = r"d:/project/graphify/encyclopedia_mockup.html"

if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR)

reader = PdfReader(PDF_PATH)
extracted_species = []
used_pages = set()

print("Launching GOLDEN RULE Rebuild (p12 = 섬백리향)...")

with open(TOC_PATH, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

current_family = "미분류"

for line in lines:
    line = line.strip()
    if not line: continue
    
    # Family tracking
    family_match = re.search(r'([가-힣]+과)\s*$', line)
    if family_match:
        current_family = family_match.group(1)
        continue

    # Name Clean
    ko_match = re.search(r'([가-힣]{2,})', line)
    if not ko_match: continue
    name = ko_match.group(1)
    
    # Page logic (Golden Rule: 섬백리향 12, 백리향 14)
    page_val = None
    if name == "섬백리향": page_val = 12
    elif name == "백리향": page_val = 14
    else:
        # Improved digit parsing for problematic TOC text
        nums = re.findall(r'(\d+)', line)
        if len(nums) >= 2:
            # Often it's [ID, Page]
            page_candidate = int(nums[-1])
            if 14 < page_candidate < 417:
                page_val = page_candidate
    
    if not page_val or page_val in used_pages: continue
    if page_val < 12: continue
    
    used_pages.add(page_val)
    
    # Extract 2-Page Image Set (N and N+1)
    paths = []
    found_any = False
    
    # A species spreads across 2 pages according to user "12, 13세트"
    for offset in [0, 1]:
        p_idx = page_val + offset - 1
        if p_idx >= len(reader.pages): continue
        
        # Capture the BIGGEST image from each page in the set
        p_imgs = sorted([i.data for i in reader.pages[p_idx].images if len(i.data) > 15000], key=len, reverse=True)
        if p_imgs:
            iname = f"{name}_{offset + 1}.png"
            with open(os.path.join(OUTPUT_DIR, iname), "wb") as f:
                f.write(p_imgs[0])
            paths.append(f"assets/species/{iname}")
            found_any = True

    if found_any:
        extracted_species.append({
            "name": name,
            "scientific_name": "Scientific Name",
            "family": current_family,
            "images": paths,
            "summary": f"{name}의 정밀 도감 데이터입니다. (도감 {page_val}-{page_val+1}쪽)",
            "details": { "분류": current_family, "페이지": f"{page_val}-{page_val+1}" }
        })

# Sync to HTML
json_data = json.dumps({"species": extracted_species}, ensure_ascii=False, indent=2)
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

new_html = re.sub(r'<script id="botanicalData" type="application/json">.*?</script>',
                 f'<script id="botanicalData" type="application/json">{json_data}</script>',
                 html, flags=re.DOTALL)

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f"Bespoke Reconstruction Complete. Total: {len(extracted_species)} species.")
