import json
import re
import os

with open("botanical_index.json", "r", encoding="utf-8") as f:
    data = json.load(f)

new_json = json.dumps(data, ensure_ascii=False, indent=2)

for target in ["d:/project/graphify/encyclopedia_mockup.html", "d:/project/graphify/index.html", "d:/project/graphify/koreantree.html"]:
    if not os.path.exists(target): continue
    with open(target, "r", encoding="utf-8") as f:
        html = f.read()
    
    updated_html = re.sub(r'<script id="botanicalData".*?>.*?</script>', 
                  f'<script id="botanicalData" type="application/json">{new_json}</script>', 
                  html, flags=re.DOTALL)
    
    with open(target, "w", encoding="utf-8") as f:
        f.write(updated_html)
    print(f"Updated: {target}")

print(f"HTML updated with {len(data['species'])} species.")
