import os
import json
import re

# Paths
IMG_DIR = r"d:/project/graphify/assets/species"
HTML_PATH = r"d:/project/graphify/encyclopedia_mockup.html"

# Load existing JSON for names
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()
raw_json = re.search(r'<script id="botanicalData" type="application/json">(.*?)</script>', html, flags=re.DOTALL)
known_data = json.loads(raw_json.group(1)) if raw_json else {"species": []}
known_map = { sp.get("physical_page", -1): sp for sp in known_data["species"] }

# Index all extracted raw images: raw_[page]_[idx].png
all_files = os.listdir(IMG_DIR)
page_groups = {}
for f in all_files:
    m = re.match(r'raw_(\d+)_(\d+)\.png', f)
    if m:
        p = int(m.group(1))
        if p not in page_groups: page_groups[p] = []
        page_groups[p].append(f"assets/species/{f}")

# Sort images within groups (optional, usually idx 0 is biggest)
for p in page_groups: page_groups[p].sort()

final_species = []
for p in sorted(page_groups.keys()):
    if p in known_map:
        # Update known species with these visuals
        sp = known_map[p]
        sp["images"] = page_groups[p]
        final_species.append(sp)
    else:
        # Create mystery entry
        final_species.append({
            "name": f"식물 자산 (PDF {p}쪽)",
            "scientific_name": "Scientific Name TBD",
            "family": "미분류 자산",
            "images": page_groups[p],
            "summary": f"PDF {p}페이지에서 추출된 식물 자산입니다. 상세 텍스트는 인코딩 복구 중입니다.",
            "details": { "상태": "데이터 복구 중", "출처": f"PDF {p}페이지" }
        })

# Save back to HTML
json_str = json.dumps({"species": final_species}, ensure_ascii=False, indent=2)
new_html = re.sub(r'<script id="botanicalData" type="application/json">.*?</script>',
                 f'<script id="botanicalData" type="application/json">{json_str}</script>',
                 html, flags=re.DOTALL)

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f"Final Build Done: {len(final_species)} species/pages integrated into grid.")
