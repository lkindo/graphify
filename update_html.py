import json
import re

# Load the extracted data
with open("botanical_index.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Load the HTML
with open("d:/project/graphify/encyclopedia_mockup.html", "r", encoding="utf-8") as f:
    html = f.read()

# Replace the content of <script id="botanicalData">
new_json = json.dumps(data, ensure_ascii=False, indent=2)
html = re.sub(r'<script id="botanicalData">.*?</script>', 
              f'<script id="botanicalData">{new_json}</script>', 
              html, flags=re.DOTALL)

# Save the updated HTML
with open("d:/project/graphify/encyclopedia_mockup.html", "w", encoding="utf-8") as f:
    f.write(html)

print("HTML updated.")
