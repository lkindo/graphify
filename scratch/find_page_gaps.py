import fitz
import re
import json

def find_gaps():
    doc = fitz.open("pdf/flower.pdf")
    page_numbers = []
    for i in range(len(doc)):
        page = doc[i]
        # Look for a number at the bottom (usually last block)
        text = page.get_text().strip()
        lines = text.split('\n')
        # Find the last line that is just a number
        found = False
        for line in reversed(lines):
            line = line.strip()
            if re.fullmatch(r'\d+', line):
                page_numbers.append({"physical": i+1, "bottom": int(line)})
                found = True
                break
        if not found:
            page_numbers.append({"physical": i+1, "bottom": None})
            
    with open("flower_page_map.json", "w", encoding="utf-8") as f:
        json.dump(page_numbers, f, ensure_ascii=False, indent=4)
    print(f"Mapped {len(page_numbers)} pages. Check flower_page_map.json")

if __name__ == "__main__":
    find_gaps()
