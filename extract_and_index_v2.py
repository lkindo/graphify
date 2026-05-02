import pypdf
import os
import re
import json

def clean_korean(text):
    # Keep only Korean characters
    return "".join(re.findall(r'[가-힣]+', text))

def extract_botanical_data_v2(pdf_path, toc_pages, content_range, offset):
    reader = pypdf.PdfReader(pdf_path)
    
    # 1. Parse TOC to get approximate names and page numbers
    toc_entries = []
    # Regex to catch: optional index, Korean name, scientific name (ignored), separator, page
    toc_re = re.compile(r'(?:\d+)?\s*([가-힣\s]{2,})\s+[a-zA-Z\s\.]{5,}.*?[•.]\s*(\d+)')
    
    last_page = 19
    for p_num in toc_pages:
        text = reader.pages[p_num - 1].extract_text()
        if not text: continue
        for line in text.splitlines():
            line = line.strip()
            match = toc_re.search(line)
            if match:
                approx_name = match.group(1).strip()
                page = int(match.group(2))
                toc_entries.append({"approx_name": approx_name, "page": page + offset})
    
    # 2. Extract Names from Content Pages using TOC hints
    plants = []
    for entry in toc_entries:
        p_num = entry['page']
        if not (content_range[0] <= p_num <= content_range[1]): continue
        
        page_obj = reader.pages[p_num - 1]
        text = page_obj.extract_text()
        if not text: continue
        
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        
        # Look for the best match for entry['approx_name'] in the first 15 lines
        best_name = clean_korean(entry['approx_name']) # Fallback
        for j in range(min(15, len(lines))):
            line = lines[j]
            k_line = clean_korean(line)
            # Avoid family names (usually end in '과')
            if k_line.endswith('과') and len(k_line) > 2:
                continue
            
            # If the TOC name is inside this line, it's likely the full correct name
            if clean_korean(entry['approx_name']) in k_line:
                if 2 <= len(k_line) <= 12:
                    best_name = k_line
                    break
        
        # Manual fix for known problematic cases
        if best_name == "소칠": best_name = "소철"
        if best_name == "태리포플러": best_name = "이태리포플러"
        
        plants.append({"name": best_name, "page": p_num})
            
    # 3. Extract Images and build result
    output_dir = "assets/species"
    if os.path.exists(output_dir):
        for f in os.listdir(output_dir):
            try: os.remove(os.path.join(output_dir, f))
            except: pass
    os.makedirs(output_dir, exist_ok=True)
    
    species_list = []
    for i, plant in enumerate(plants):
        start_p = plant['page']
        # The next plant starts at plants[i+1]['page']
        end_p = plants[i+1]['page'] - 1 if i+1 < len(plants) else content_range[1]
        
        img_filenames = []
        
        # The user said: "각 나무당 관련이미지는 2개씩이야"
        # So we collect exactly 2 images across the page range.
        found_images = 0
        for p in range(start_p, end_p + 1):
            if found_images >= 2: break
            
            page_obj = reader.pages[p - 1]
            if '/Resources' in page_obj and '/XObject' in page_obj['/Resources']:
                xObject = page_obj['/Resources']['/XObject'].get_object()
                # Sort objects to maintain some order (heuristic)
                for obj in sorted(xObject.keys()):
                    if found_images >= 2: break
                    
                    if xObject[obj]['/Subtype'] == '/Image':
                        try:
                            data = xObject[obj].get_data()
                            if len(data) < 20000: continue # Skip icons (<20KB)
                            
                            found_images += 1
                            fname = f"{plant['name']}_{found_images}.jpg"
                            with open(os.path.join(output_dir, fname), "wb") as f:
                                f.write(data)
                            img_filenames.append(fname)
                        except:
                            continue
        
        if img_filenames:
            species_list.append({
                "name": plant['name'],
                "category": "한국의 나무",
                "image": f"assets/species/{img_filenames[0]}",
                "summary": f"{plant['name']}에 대한 도감 정보입니다.",
                "details": f"PDF {start_p}페이지에 위치한 {plant['name']}의 정밀 사진입니다."
            })
            print(f"Extracted: {plant['name']} (Page {start_p}, {len(img_filenames)} images)")

    return species_list

pdf_path = "d:/project/graphify/pdf/koreantree1.pdf"
results = extract_botanical_data_v2(pdf_path, [17, 18, 19, 20], [21, 409], 1)

with open("botanical_index.json", "w", encoding="utf-8") as f:
    json.dump({"species": results}, f, ensure_ascii=False, indent=2)
