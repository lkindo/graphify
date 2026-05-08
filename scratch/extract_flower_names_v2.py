import fitz
import re
import json

def clean_name(text):
    if not text: return ""
    text = text.strip()
    # Remove weird prefixes
    text = re.sub(r'^[!\?~\-，\|\s]+', '', text)
    # Remove junk at the end
    text = re.sub(r'[\s!]+$', '', text)
    # Filter out known junk characters
    if any(c in text for c in "훌흩롤훨쩔뀔훤鋼"):
        return ""
    # Filter out known stop words
    stop_words = ["꽃말", "낙엽교목", "수고", "분포", "유래", "앙성화", "취산", "원추", "충매화", "꽃차례", "거꿀달갈형", "타원형", "꽃잎", "수술", "암술"]
    for sw in stop_words:
        if sw in text: return ""
    
    # Keep only Korean
    text = "".join(re.findall(r'[가-힣]+', text))
    
    if len(text) < 2 or len(text) > 10: return ""
    return text

def extract_from_origin(text):
    # Search for common patterns in the "유래" section
    patterns = [
        r"['‘]([^'’]+)['’]", # Text in single quotes
        r"([가-힣]+)(?:가|이) 된 것",
        r"([가-힣]+)(?:라|이라) 부르다가",
        r"([가-힣]+)(?:로|으로) 변한 것",
        r"([가-힣]+)(?:라|이라) 하여",
        r"([가-힣]+)(?:이|가) 붙여진 이름",
        r"([가-힣]+)(?:이|가) 붙은 이름",
        r"([가-힣]+)라 고 부르기도 한다",
        r"([가-힣]+)라고도 부른다"
    ]
    
    origin_line = ""
    for line in text.split('\n'):
        if '유래' in line:
            origin_line = line
            break
    
    if not origin_line:
        return None
        
    for p in patterns:
        match = re.search(p, origin_line)
        if match:
            name = match.group(1)
            if 2 <= len(name) <= 10:
                return name
    return None

def extract_species_names():
    doc = fitz.open("pdf/flower.pdf")
    results = []
    
    for i in range(len(doc)):
        page = doc[i]
        full_text = page.get_text()
        
        # 1. Try "Origin" section
        name = extract_from_origin(full_text)
        
        # 2. Try top header if Origin failed
        if not name:
            blocks = page.get_text("dict")["blocks"]
            candidates = []
            for b in blocks:
                if "lines" not in b: continue
                for l in b["lines"]:
                    for s in l["spans"]:
                        if s["bbox"][1] < 150: # Top 150px
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
            
        results.append({"page": i+1, "name": name})
    
    with open("flower_naming_report_v2.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    print(f"Extracted {len(results)} names. Check flower_naming_report_v2.json")

if __name__ == "__main__":
    extract_species_names()
