import fitz
import os
import re
import json

# Manual overrides for the first few pages and common errors
MANUAL_OVERRIDES = {
    3: "노각나무",
    4: "느릅나무",
    5: "말채나무",
    7: "멀구슬나무",
    8: "목련",
    9: "백목련",
    10: "백합나무",
    11: "산딸나무",
    13: "아까시나무",
    15: "오리나무",
    16: "자작나무",
    17: "참나무",
    27: "가시나무", # Example fallback
}

def clean_name(text):
    if not text: return ""
    text = text.strip()
    text = "".join(re.findall(r'[가-힣]+', text))
    junk_chars = "훌흩롤훨쩔뀔훤鋼댈략젤첼펀퀀돼딛텡"
    if any(c in text for c in junk_chars): return ""
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
    if not origin_line: return None
    patterns = [
        r"['‘]([^'’]+)['’]",
        r"([가-힣]+)(?:가|이)\s*된\s*것",
        r"([가-힣]+)(?:라|이라)\s*부르다가",
        r"([가-힣]+)(?:로|으로)\s*변한\s*것",
        r"([가-힣]+)(?:라|이라)\s*하여",
        r"([가-힣]+)(?:이|가)\s*붙여진\s*이름",
        r"([가-힣]+)(?:이|가)\s*붙은\s*이름",
        r"([가-힣]+)\s*라고도\s*부른다",
        r"([가-힣]+)\s*라\s*부르기도\s*한다"
    ]
    for p in patterns:
        match = re.search(p, origin_line)
        if match:
            name = "".join(re.findall(r'[가-힣]+', match.group(1)))
            if 2 <= len(name) <= 10: return name
    return None

def main():
    doc = fitz.open("pdf/flower.pdf")
    output_dir = "assets/flowers"
    os.makedirs(output_dir, exist_ok=True)
    
    # Remove existing images to avoid confusion
    for f in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, f))
        
    species_list = []
    
    for i in range(len(doc)):
        page = doc[i]
        page_num = i + 1
        
        # 1. Manual Override
        name = MANUAL_OVERRIDES.get(page_num)
        
        # 2. Origin Section
        if not name:
            name = extract_from_origin(page.get_text())
            
        # 3. Header Size
        if not name:
            blocks = page.get_text("dict")["blocks"]
            candidates = []
            for b in blocks:
                if "lines" not in b: continue
                for l in b["lines"]:
                    for s in l["spans"]:
                        if s["bbox"][1] < 150:
                            c_name = clean_name(s["text"])
                            if c_name:
                                candidates.append({"name": c_name, "size": s["size"], "y": s["bbox"][1]})
            candidates.sort(key=lambda x: (-x["size"], x["y"]))
            if candidates:
                name = candidates[0]["name"]
        
        # 4. Fallback
        if not name:
            name = f"page_{page_num}"
            
        # Final name safety
        name = name.replace(" ", "")
        
        # Extract Image
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_path = f"{output_dir}/{name}.png"
        
        # Handle duplicates
        counter = 1
        original_name = name
        while os.path.exists(img_path):
            name = f"{original_name}_{counter}"
            img_path = f"{output_dir}/{name}.png"
            counter += 1
            
        pix.save(img_path)
        
        species_list.append({
            "name": name,
            "category": "나무에 피는 꽃",
            "images": [img_path],
            "summary": f"{name}에 대한 정보입니다.",
            "details": f"{name}의 도감 페이지입니다."
        })
        print(f"Page {page_num} -> {name}")
        
    # Save Index
    with open("flower_index.json", "w", encoding="utf-8") as f:
        json.dump({"species": species_list}, f, ensure_ascii=False, indent=4)
        
    print("Extraction and Naming Complete!")

if __name__ == "__main__":
    main()
