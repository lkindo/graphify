import fitz
import re
import json

def clean_name(text):
    if not text: return ""
    text = text.strip()
    # Keep only Korean
    text = "".join(re.findall(r'[가-힣]+', text))
    
    # Filter out junk characters often seen in OCR errors
    junk_chars = "훌흩롤훨쩔뀔훤鋼댈략젤첼펀퀀돼딛텡"
    if any(c in text for c in junk_chars):
        return ""
        
    # Filter out common noise words
    stop_words = ["꽃말", "낙엽교목", "수고", "분포", "유래", "앙성화", "취산", "원추", "충매화", "꽃차례", "거꿀달갈형", "타원형", "꽃잎", "수술", "암술", "마주나며", "어긋나며", "작은잎"]
    for sw in stop_words:
        if sw in text: return ""
        
    if len(text) < 2 or len(text) > 8: return ""
    return text

def extract_from_origin(text):
    origin_line = ""
    for line in text.split('\n'):
        if '유래' in line:
            origin_line = line
            break
    
    if not origin_line:
        return None
        
    # Patterns for "Origin" section
    patterns = [
        r"['‘]([^'’]+)['’]", # Text in single quotes
        r"([가-힣]+)(?:가|이)\s+된\s+것",
        r"([가-힣]+)(?:라|이라)\s+부르다가",
        r"([가-힣]+)(?:로|으로)\s+변한\s+것",
        r"([가-힣]+)(?:라|이라)\s+하여",
        r"([가-힣]+)(?:이|가)\s+붙여진\s+이름",
        r"([가-힣]+)(?:이|가)\s+붙은\s+이름",
        r"([가-힣]+)\s*라고도\s+부른다",
        r"([가-힣]+)\s*라\s+부르기도\s+한다"
    ]
    
    for p in patterns:
        match = re.search(p, origin_line)
        if match:
            name = match.group(1).strip()
            # Clean non-Korean from the result
            name = "".join(re.findall(r'[가-힣]+', name))
            if 2 <= len(name) <= 10:
                return name
    return None

def extract_species_names():
    doc = fitz.open("pdf/flower.pdf")
    results = []
    
    for i in range(len(doc)):
        page = doc[i]
        full_text = page.get_text()
        
        # 1. Try "Origin" section first (High confidence)
        name = extract_from_origin(full_text)
        
        # 2. Try top header if Origin failed (Medium confidence)
        if not name:
            blocks = page.get_text("dict")["blocks"]
            candidates = []
            for b in blocks:
                if "lines" not in b: continue
                for l in b["lines"]:
                    for s in l["spans"]:
                        if s["bbox"][1] < 120: # Even stricter top area
                            c_name = clean_name(s["text"])
                            if c_name:
                                candidates.append({
                                    "name": c_name,
                                    "size": s["size"],
                                    "y": s["bbox"][1]
                                })
            candidates.sort(key=lambda x: (-x["size"], x["y"]))
            if candidates:
                name = candidates[0]["name"]
        
        # 3. Final Fallback
        if not name:
            name = f"page_{i+1}"
            
        # Last minute cleanup
        if name:
            name = name.replace(" ", "")
            if name.endswith("과") and len(name) > 3:
                name = name[:-1]
                
        results.append({"page": i+1, "name": name})
    
    with open("flower_naming_report_v3.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    print(f"Extracted {len(results)} names. Check flower_naming_report_v3.json")

if __name__ == "__main__":
    extract_species_names()
