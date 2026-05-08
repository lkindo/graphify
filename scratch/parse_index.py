import fitz
import re
import json

def parse_index_with_coords():
    doc = fitz.open("pdf/index.pdf")
    entries = []
    
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        # Collect all spans with their center-y and x
        spans = []
        for b in blocks:
            if "lines" not in b: continue
            for l in b["lines"]:
                for s in l["spans"]:
                    text = s["text"].strip()
                    if not text: continue
                    spans.append({
                        "text": text,
                        "x": s["bbox"][0],
                        "y": (s["bbox"][1] + s["bbox"][3]) / 2,
                        "size": s["size"]
                    })
        
        # Sort by y, then x
        spans.sort(key=lambda s: (s["y"], s["x"]))
        
        # Look for Name (text) and Number (digits) that are on roughly same Y
        # or sequential in the list
        for i in range(len(spans) - 1):
            s1 = spans[i]
            s2 = spans[i+1]
            
            # Check if s1 is a name and s2 is a number, or vice versa
            is_num1 = re.fullmatch(r'\d+', s1["text"])
            is_num2 = re.fullmatch(r'\d+', s2["text"])
            
            if not is_num1 and is_num2:
                # Name then Number
                # Check if they are on same line or close
                if abs(s1["y"] - s2["y"]) < 10:
                    entries.append({"name": s1["text"], "page": int(s2["text"])})
            elif is_num1 and not is_num2:
                # Number then Name? (Less likely but possible)
                if abs(s1["y"] - s2["y"]) < 10:
                    pass # Ignore for now
    
    # Sort and clean
    entries.sort(key=lambda x: x["page"])
    return entries

def main():
    entries = parse_index_with_coords()
    with open("parsed_index.json", "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=4)
    print(f"Parsed {len(entries)} entries from index.pdf")

if __name__ == "__main__":
    main()
