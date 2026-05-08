import fitz
import re
import json

def parse_index_v3():
    doc = fitz.open("pdf/index.pdf")
    all_entries = []
    
    for page in doc:
        # Sort all spans by y, then x
        spans = []
        for b in page.get_text("dict")["blocks"]:
            if "lines" not in b: continue
            for l in b["lines"]:
                for s in l["spans"]:
                    text = s["text"].strip()
                    if text:
                        spans.append({
                            "text": text,
                            "x": s["bbox"][0],
                            "y": (s["bbox"][1] + s["bbox"][3]) / 2
                        })
        
        spans.sort(key=lambda s: (s["y"], s["x"]))
        
        # Group by Y (same line)
        lines = []
        if not spans: continue
        
        current_line = [spans[0]]
        for i in range(1, len(spans)):
            if abs(spans[i]["y"] - current_line[-1]["y"]) < 5:
                current_line.append(spans[i])
            else:
                lines.append(current_line)
                current_line = [spans[i]]
        lines.append(current_line)
        
        # In each line, look for Name and Number
        # Sometimes they are separate spans, sometimes together
        for line in lines:
            line.sort(key=lambda s: s["x"])
            # Filter out very small artifacts
            line = [s for s in line if len(s["text"]) > 0]
            
            # Simple pairing: if we see a string and then a number
            for i in range(len(line) - 1):
                s1 = line[i]
                s2 = line[i+1]
                
                # Case 1: Name (s1) and Number (s2)
                if not s1["text"].isdigit() and s2["text"].isdigit():
                    name = s1["text"]
                    page_num = int(s2["text"])
                    if 10 <= page_num <= 350:
                        all_entries.append({"name": name, "page": page_num})
                
                # Case 2: Both in one span? (e.g. "개오동 10")
                match = re.search(r'([가-힣\s\.\*tL\+]+)\s+(\d+)$', s1["text"])
                if match:
                    name = match.group(1).strip()
                    page_num = int(match.group(2))
                    if 10 <= page_num <= 350:
                        all_entries.append({"name": name, "page": page_num})

    # Deduplicate and Clean
    cleaned = {}
    for e in all_entries:
        name = "".join(re.findall(r'[가-힣]+', e["name"]))
        if name and len(name) >= 2:
            # Keep the first name found for a page, or best match
            if e["page"] not in cleaned or len(name) > len(cleaned[e["page"]]):
                cleaned[e["page"]] = name
                
    return [{"name": v, "page": k} for k, v in sorted(cleaned.items())]

def main():
    entries = parse_index_v3()
    with open("master_index.json", "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=4)
    print(f"Extracted {len(entries)} entries for master index.")

if __name__ == "__main__":
    main()
