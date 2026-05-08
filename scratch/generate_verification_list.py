import fitz
import re
import json

def clean_name(text):
    if not text: return ""
    text = text.strip()
    text = "".join(re.findall(r'[가-힣]+', text))
    junk_chars = "훌흩롤훨쩔뀔훤鋼댈략젤첼펀퀀돼딛텡"
    if any(c in text for c in junk_chars): return ""
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
    # 1. Load Master Index (if exists)
    master_dict = {}
    try:
        with open("master_index.json", "r", encoding="utf-8") as f:
            master_data = json.load(f)
        master_dict = {item["page"]: item["name"] for item in master_data}
    except:
        pass
        
    full_index_map = {}
    last_name = "미확인"
    for p in range(1, 350):
        if p in master_dict:
            last_name = master_dict[p]
        full_index_map[p] = last_name
        
    # 2. Load Page Map (if exists)
    page_map = {}
    try:
        with open("flower_page_map.json", "r", encoding="utf-8") as f:
            page_map_raw = json.load(f)
        for i in range(len(page_map_raw)):
            if page_map_raw[i]["bottom"] is None:
                if i > 0 and page_map_raw[i-1]["bottom"] is not None:
                    page_map_raw[i]["bottom"] = page_map_raw[i-1]["bottom"] + 1
                elif i < len(page_map_raw)-1 and page_map_raw[i+1]["bottom"] is not None:
                    page_map_raw[i]["bottom"] = page_map_raw[i+1]["bottom"] - 1
        page_map = {item["physical"]: item["bottom"] for item in page_map_raw}
    except:
        pass
    
    doc = fitz.open("pdf/flower.pdf")
    verification_lines = []
    
    for i in range(len(doc)):
        page = doc[i]
        phys_num = i + 1
        bottom_num = page_map.get(phys_num)
        
        # Priority 1: Origin
        name = extract_from_origin(page.get_text())
        
        # Priority 2: Index
        if not name:
            name = full_index_map.get(bottom_num)
            
        if not name or name == "미확인":
            name = "이름확인필요"
            
        name = clean_name(name) or name
        verification_lines.append(f"{phys_num}, {name}")
        
    with open("species_verification.md", "w", encoding="utf-8") as f:
        f.write("# Species Name Verification\n")
        f.write("물리적페이지, 나무명\n")
        f.write("\n".join(verification_lines))
        
    print("Verification file created: species_verification.md")

if __name__ == "__main__":
    main()
