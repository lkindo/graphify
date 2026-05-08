import fitz
import os
import re
import json

def clean_name(text):
    if not text: return ""
    text = text.strip()
    text = "".join(re.findall(r'[가-힣]+', text))
    junk_chars = "훌흩롤훨쩔뀔훤鋼댈략젤첼펀퀀돼딛텡"
    if any(c in text for c in junk_chars): return ""
    stop_words = ["꽃말", "낙엽교목", "수고", "분포", "유래", "앙성화", "취산", "원추", "충매화", "꽃차례", "거꿀달갈형", "타원형", "꽃잎", "수술", "암술", "마주나며", "어긋나며", "작은잎"]
    for sw in stop_words:
        if sw in text: return ""
    if len(text) < 2 or len(text) > 10: return ""
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
    # Load mappings
    with open("cleaned_index.json", "r", encoding="utf-8") as f:
        index_data = json.load(f)
    index_map = {item["page"]: item["name"] for item in index_data}
    
    with open("flower_page_map.json", "r", encoding="utf-8") as f:
        page_map_raw = json.load(f)
    
    # Fill null bottom page numbers
    for i in range(len(page_map_raw)):
        if page_map_raw[i]["bottom"] is None:
            if i > 0 and page_map_raw[i-1]["bottom"] is not None:
                page_map_raw[i]["bottom"] = page_map_raw[i-1]["bottom"] + 1
            elif i < len(page_map_raw)-1 and page_map_raw[i+1]["bottom"] is not None:
                page_map_raw[i]["bottom"] = page_map_raw[i+1]["bottom"] - 1
                
    page_map = {item["physical"]: item["bottom"] for item in page_map_raw}
    
    doc = fitz.open("pdf/flower.pdf")
    output_dir = "assets/flowers"
    os.makedirs(output_dir, exist_ok=True)
    
    # Clear existing
    for f in os.listdir(output_dir):
        if f.endswith(".png"): os.remove(os.path.join(output_dir, f))
        
    species_list = []
    
    for i in range(len(doc)):
        page = doc[i]
        phys_num = i + 1
        bottom_num = page_map.get(phys_num)
        
        # 1. Try Index mapping
        name = index_map.get(bottom_num)
        
        # 2. Try Origin fallback if index failed or name looks too short/generic
        if not name or len(name) < 2:
            name = extract_from_origin(page.get_text())
            
        # 3. Final Fallback to page number if still nothing
        if not name:
            name = f"page_{bottom_num if bottom_num else phys_num}"
            
        # Extract Image
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_name = f"{name}.png"
        img_path = f"{output_dir}/{img_name}"
        
        # Handle duplicates
        counter = 1
        base_name = name
        while os.path.exists(img_path):
            img_name = f"{base_name}_{counter}.png"
            img_path = f"{output_dir}/{img_name}"
            counter += 1
            
        pix.save(img_path)
        
        species_list.append({
            "name": img_name.replace(".png", ""),
            "category": "나무에 피는 꽃",
            "images": [f"assets/flowers/{img_name}"],
            "summary": f"{name}에 대한 정보입니다. (페이지 {bottom_num})",
            "details": f"{name}의 도감 페이지입니다."
        })
        print(f"Phys {phys_num} (Bottom {bottom_num}) -> {img_name}")
        
    # Save Final Index
    with open("flower_index.json", "w", encoding="utf-8") as f:
        json.dump({"species": species_list}, f, ensure_ascii=False, indent=4)
        
    print("Final Extraction based on index.pdf complete!")

if __name__ == "__main__":
    main()
