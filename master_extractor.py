import pypdf
import os
import re
import json
import shutil

def clean_korean(text):
    return re.sub(r'[^가-힣]', '', text)

def extract_from_pdf(pdf_path, category, global_results, toc_pages, content_range):
    print(f"Processing {pdf_path}...")
    try:
        reader = pypdf.PdfReader(pdf_path)
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return

    print(f"TOC pages: {toc_pages}")
    
    toc_entries = []
    # Regex 1: [Korean] ... [Page] (with various separators)
    entry_re = re.compile(r'([가-힣|]{2,})\s*.*?[•.·\'\s]\s*(\d{1,3})(?!\d)')
    # Regex 2: Start of line [Korean] (fallback)
    fallback_re = re.compile(r'^(\d{2,3})?\s*([가-힣]{2,})')
    
    last_page = 0
    
    for p_num in toc_pages:
        text = reader.pages[p_num - 1].extract_text()
        if not text: continue
        for line in text.splitlines():
            line = line.strip()
            if not line or any(x in line for x in ["차례", "부록", "찾아보기", "일러두기"]): continue
                
            matches = list(entry_re.finditer(line))
            if matches:
                for match in matches:
                    name = match.group(1).replace("|", "").strip()
                    page = int(match.group(2))
                    if len(name) < 2 or name.endswith("과"): continue
                    toc_entries.append({"approx_name": name, "page": page + 1})
                    last_page = page
            else:
                match = fallback_re.search(line)
                if match:
                    name = match.group(2).replace("|", "").strip()
                    if len(name) < 2 or name.endswith("과"): continue
                    # Only fallback if we can guess a reasonable page
                    if last_page > 0:
                        page = last_page + 2
                        toc_entries.append({"approx_name": name, "page": page + 1})
                        last_page = page

    # Manual overrides for problematic entries in Vol 1 & 4
    if "koreantree1" in pdf_path:
        toc_entries.append({"approx_name": "메타세쿼이아", "page": 91})
        toc_entries.append({"approx_name": "낙우송", "page": 93})
        toc_entries.append({"approx_name": "가이즈카향나무", "page": 97})
        toc_entries.append({"approx_name": "만주곰솔", "page": 77})
        toc_entries.append({"approx_name": "잣나무", "page": 79})
        toc_entries.append({"approx_name": "섬잣나무", "page": 81})
        toc_entries.append({"approx_name": "당버들", "page": 159})
        toc_entries.append({"approx_name": "오리나무", "page": 211})
        toc_entries.append({"approx_name": "소사나무", "page": 233})
        toc_entries.append({"approx_name": "물갬나무", "page": 207})
        toc_entries.append({"approx_name": "물참나무", "page": 265})
        toc_entries.append({"approx_name": "백목련", "page": 345})
        toc_entries.append({"approx_name": "납매", "page": 371})
        toc_entries.append({"approx_name": "뇌성목", "page": 383})
        toc_entries.append({"approx_name": "계수나무", "page": 393})
    if "koreantree2" in pdf_path:
        toc_entries.append({"approx_name": "물참대", "page": 97})
        toc_entries.append({"approx_name": "일본매자나무", "page": 23})
    if "koreantree3" in pdf_path:
        toc_entries.append({"approx_name": "새비나무", "page": 311})
        toc_entries.append({"approx_name": "백정화", "page": 301})
        toc_entries.append({"approx_name": "좁은잎계요등", "page": 299})
        toc_entries.append({"approx_name": "누리장나무", "page": 313})
        toc_entries.append({"approx_name": "개나리", "page": 181})
        toc_entries.append({"approx_name": "광릉물푸레", "page": 207})
        toc_entries.append({"approx_name": "구슬댕댕이", "page": 353})
        toc_entries.append({"approx_name": "숯명다래나무", "page": 359})
    if "koreantree4" in pdf_path:
        # Add missing ones
        toc_entries.append({"approx_name": "구기자나무", "page": 17})
        toc_entries.append({"approx_name": "회목나무", "page": 285})
        toc_entries.append({"approx_name": "회잎나무", "page": 277})
        toc_entries.append({"approx_name": "복자기", "page": 197})
        # Fix ones with wrong inferred pages
        for entry in toc_entries:
            if "능소화" == entry['approx_name']: entry['page'] = 29
        
    # Deduplicate and sort
    seen = set()
    final_toc = []
    for e in sorted(toc_entries, key=lambda x: x['page']):
        name_key = e['approx_name'].strip()
        if name_key not in seen:
            final_toc.append(e)
            seen.add(name_key)

    output_dir = "assets/species"
    os.makedirs(output_dir, exist_ok=True)
    
    plants = []
    for entry in final_toc:
        p_num = entry['page']
        if not (content_range[0] <= p_num <= content_range[1]): continue
        
        try:
            if p_num > len(reader.pages): continue
            target_p = p_num
            page_obj = reader.pages[target_p - 1]
            text = page_obj.extract_text()
            
            # Skip empty pages
            if not text or len(clean_korean(text)) < 5:
                if target_p < len(reader.pages):
                    next_text = reader.pages[target_p].extract_text()
                    if next_text and len(clean_korean(next_text)) > 5:
                        target_p += 1
                        page_obj = reader.pages[target_p - 1]
                        text = next_text

            lines = [l.strip() for l in text.splitlines() if l.strip()]
            approx_name_clean = clean_korean(entry['approx_name'])
            
            # OCR Corrections
            if "광광나무" in approx_name_clean: approx_name_clean = approx_name_clean.replace("광광나무", "꽝꽝나무")
            if "호목나무" in approx_name_clean: approx_name_clean = approx_name_clean.replace("호목나무", "회목나무")
            if "횡황" in approx_name_clean: approx_name_clean = "황금측백나무"
            if "물침" in approx_name_clean: approx_name_clean = "물참나무"
            if "머타" in approx_name_clean or "세쿼이아" in approx_name_clean: approx_name_clean = "메타세쿼이아"
            if "닥우송" in approx_name_clean or "낙우송" in approx_name_clean: approx_name_clean = "낙우송"
            if "가01즈카" in approx_name_clean: approx_name_clean = "가이즈카향나무"
            if "당개서어" in approx_name_clean: approx_name_clean = "소사나무"
            if "깨떼" in approx_name_clean: approx_name_clean = "납매"
            if "겨수" in approx_name_clean or "겨|수" in approx_name_clean: approx_name_clean = "계수나무"
            if "노성" in approx_name_clean or "노|성" in approx_name_clean: approx_name_clean = "뇌성목"
            
            best_name = approx_name_clean
            for j in range(min(15, len(lines))):
                k_line = clean_korean(lines[j])
                if k_line.endswith('과') and len(k_line) > 2: continue
                if "혹빽나무" in k_line: k_line = k_line.replace("혹빽나무", "측백나무")
                
                if approx_name_clean in k_line or (approx_name_clean == "황금측백나무" and "측백나무" in k_line):
                    if 2 <= len(k_line) <= 12:
                        best_name = k_line
                        break
            
            if "태리포플러" in best_name: best_name = "이태리포플러"
            if "광광나무" in best_name: best_name = best_name.replace("광광나무", "꽝꽝나무")
            if "호목나무" in best_name: best_name = best_name.replace("호목나무", "회목나무")
            if "횡황" in best_name: best_name = "황금측백나무"
            if "물침" in best_name: best_name = "물참나무"
            if "머타" in best_name or "세쿼이아" in best_name: best_name = "메타세쿼이아"
            if "닥우송" in best_name or "낙우송" in best_name: best_name = "낙우송"
            if "당개서어" in best_name: best_name = "소사나무"
            if "가01즈카" in best_name or "가이즈카" in best_name: best_name = "가이즈카향나무"
            if "구기자나무" in best_name: best_name = "구기자나무"
            if "납매" in best_name or "깨떼" in best_name: best_name = "납매"
            if "겨수" in best_name: best_name = "계수나무"
            if "노성" in best_name: best_name = "뇌성목"
            if "물검" in best_name: best_name = "물갬나무"
            
            # Volume-specific overrides
            pdf_filename = os.path.basename(pdf_path)
            if pdf_filename == "koreantree1.pdf":
                if best_name == "물검나무": best_name = "물갬나무"
                if best_name == "만주곰솔": target_p = 77
                if best_name == "잣나무": target_p = 79
                if best_name == "섬잣나무": target_p = 81
                if best_name == "당버들": target_p = 159
                if best_name == "물갬나무": target_p = 207
                if best_name == "오리나무": target_p = 211
                if best_name == "백목련": target_p = 345
                if "수앙" in best_name: best_name = best_name.replace("수앙", "수양")
                if best_name == "주목매": best_name = "주목"
            
            elif pdf_filename == "koreantree2.pdf":
                # Vol 2 corrections
                if "닮잎으름" in best_name: best_name = "여덟잎으름"
                if best_name == "등칩": best_name = "등칡"
                if best_name == "디띠띠": best_name = "쥐다래"
                if best_name == "땅나무": best_name = "다래"
                if best_name == "멀궐": best_name = "멀꿀"
                if best_name == "멍멍이덩굴": best_name = "댕댕이덩굴"
                if best_name == "팔배나무": best_name = "팥배나무"
                if best_name == "죽단호": best_name = "죽단화"
                if best_name == "복분자띨": best_name = "복분자딸기"
                if "홍매호화" in best_name: best_name = "홍매화"
                if "흰만접" in best_name: best_name = "흰만첩매실"
                if best_name == "함박": best_name = "함박이"
                if "스러피" in best_name or "스러|피" in best_name: best_name = "사스레피나무"
                if best_name == "청쉬": best_name = "청쉬땅나무"
                if best_name == "세로티": best_name = "세로티나벚나무"
                if "매 자나무" in best_name: best_name = best_name.replace("매 자나무", "매자나무")
                if best_name == "일본매자나무": target_p = 23
                
                # Manual page overrides for Vol 2
                if best_name == "털새모래덩굴": target_p = 41
                if best_name == "댕댕이덩굴": target_p = 37
                if best_name == "물참대": target_p = 97
                if best_name == "조록나무": target_p = 83
                if best_name == "당조팝나무": target_p = 411
                if best_name == "덤불조팝나무": target_p = 417
                if best_name == "사스레피나무": target_p = 65
                if best_name == "우묵사스레피": target_p = 67
                if "개위봉" in best_name: target_p = 309
                if "위봉배" in best_name or "위봉님배" in best_name: target_p = 311
                if best_name == "팥배나무": target_p = 375
            elif pdf_filename == "koreantree3.pdf":
                # Vol 3 corrections
                if "겹산절죽" in best_name: best_name = "겹산철쭉"
                if "절쭉" in best_name: best_name = best_name.replace("절쭉", "철쭉")
                if best_name == "계요듬": best_name = "계요등"
                if best_name == "고용나무": best_name = "고욤나무"
                if "광름" in best_name: best_name = best_name.replace("광름", "광릉")
                if "구슬탱댐" in best_name: best_name = "구슬댕댕이"
                if "탱강나무" in best_name: best_name = best_name.replace("탱강나무", "댕강나무")
                if "댐강나무" in best_name: best_name = best_name.replace("댐강나무", "댕강나무")
                if best_name == "당개나리": best_name = "개나리"
                if "바위댐강" in best_name: best_name = "바위댕강나무"
                if best_name == "만칩협죽도": best_name = "만첩협죽도"
                if best_name == "숫염": best_name = "숯명다래나무"
                if best_name == "영춘호": best_name = "영춘화"
                if best_name == "필손이": best_name = "팔손이"
                
                # Junk removal for Vol 3
                if best_name in ["꽃개회", "섬쥐", "둥근잎섬쥐똥나무"]: continue
                
                # Manual page overrides for Vol 3
                if best_name == "겹산철쭉": target_p = 121
                if best_name == "개나리": target_p = 181
                if best_name == "광릉물푸레": target_p = 207
                if best_name == "좁은잎계요등": target_p = 299
                if best_name == "백정화": target_p = 301
                if best_name == "새비나무": target_p = 311
                if best_name == "댕강나무": target_p = 327
                if best_name == "줄댕강나무": target_p = 329
                if best_name == "꽃댕강나무": target_p = 331
                if best_name == "바위댕강나무": target_p = 333
                if best_name == "털댕강나무": target_p = 335
                if best_name == "섬댕강나무": target_p = 337
                if best_name == "누리장나무": target_p = 313
                if best_name == "구슬댕댕이": target_p = 353
                if best_name == "숯명다래나무": target_p = 359
                
            elif pdf_filename == "koreantree4.pdf":
                # Vol 4 corrections
                if best_name == "광랄": best_name = "광귤"
                if best_name == "기까": best_name = "배풍등"
                if best_name == "대빗집나무": best_name = "대팻집나무"
                if "대뱃집나무" in best_name: best_name = "대팻집나무"
                if best_name == "뱃집": best_name = "민대팻집나무"
                if best_name == "덩굴옴나무": best_name = "덩굴옻나무"
                if best_name == "러몬": best_name = "레몬"
                if "만주고로소" in best_name: best_name = best_name.replace("만주고로소", "만주고로쇠")
                if best_name == "사람추나무": best_name = "사람주나무"
                if best_name == "사절나무": best_name = "사철나무"
                if "산검양올" in best_name: best_name = "산검양옻나무"
                if best_name == "수나무": best_name = "쉬나무"
                if best_name == "연밥피": best_name = "연밥피나무"
                if best_name == "올나무": best_name = "옻나무"
                if best_name == "장실급감": best_name = "장실금감"
                if best_name == "콜담초": best_name = "골담초"
                if best_name == "핏대추나무": best_name = "묏대추나무"
                if best_name == "호입나무": best_name = "회잎나무"
                if best_name == "화태황벅나무": best_name = "화태황벽나무"
                
                # Manual page overrides for Vol 4
                if best_name == "배풍등": target_p = 19
                if best_name == "좀회양목": target_p = 311
                if best_name == "연밥피나무": target_p = 369
                if best_name == "민대팻집나무": target_p = 255
                if best_name == "대팻집나무": target_p = 253
                if best_name == "사철나무": target_p = 281
                if best_name == "회잎나무": target_p = 277
                if best_name == "복자기": target_p = 197
                if best_name == "화태황벽나무": target_p = 153
                
            plants.append({"name": best_name, "page": target_p})
        except: continue

    for i, plant in enumerate(plants):
        start_p = plant['page']
        end_p = min(start_p + 1, len(reader.pages))
        
        img_filenames = []
        found_images = 0
        for p in range(start_p, end_p + 1):
            if found_images >= 2: break
            page_obj = reader.pages[p - 1]
            if '/Resources' in page_obj and '/XObject' in page_obj['/Resources']:
                xObject = page_obj['/Resources']['/XObject'].get_object()
                page_imgs = []
                for obj in xObject:
                    if xObject[obj]['/Subtype'] == '/Image':
                        try:
                            data = xObject[obj].get_data()
                            page_imgs.append((len(data), obj, data))
                        except: continue
                
                page_imgs.sort(key=lambda x: x[0], reverse=True)
                for size, obj, data in page_imgs:
                    if found_images >= 2: break
                    if size < 10000: continue
                    found_images += 1
                    vol = os.path.basename(pdf_path).replace(".pdf", "")
                    fname = f"{vol}_{plant['name']}_{found_images}.jpg"
                    with open(os.path.join(output_dir, fname), "wb") as f:
                        f.write(data)
                    img_filenames.append(fname)
        
        if img_filenames:
            global_results.append({
                "name": plant['name'],
                "category": category,
                "images": [f"assets/species/{f}" for f in img_filenames],
                "summary": f"{plant['name']}에 대한 도감 정보입니다.",
                "details": f"{plant['name']}의 사진입니다. (출처: {os.path.basename(pdf_path)} {start_p}페이지)"
            })
            print(f"[{vol}] Extracted: {plant['name']} (Page {start_p})")

# Main Execution
all_species = []
pdf_dir = "d:/project/graphify/pdf"
output_dir = "assets/species"

# Clear output directory at the very beginning
if os.path.exists(output_dir):
    shutil.rmtree(output_dir)
os.makedirs(output_dir, exist_ok=True)

guidelines = {
    "koreantree1.pdf": {"toc": [16, 17, 18, 19, 20], "content": [21, 409]},
    "koreantree2.pdf": {"toc": [8, 9, 10, 11], "content": [12, 439]},
    "koreantree3.pdf": {"toc": [8, 9, 10, 11], "content": [12, 411]},
    "koreantree4.pdf": {"toc": [8, 9, 10, 11], "content": [12, 387]},
}

for pdf_name, config in guidelines.items():
    path = os.path.join(pdf_dir, pdf_name)
    if os.path.exists(path):
        toc_phys = [p + 1 for p in config['toc']]
        content_phys = [config['content'][0] + 1, config['content'][1] + 1]
        extract_from_pdf(path, f"한국의 나무", all_species, toc_phys, content_phys)

# Final deduplication
seen_final = set()
final_unique_species = []
for s in all_species:
    if s['name'] not in seen_final:
        final_unique_species.append(s)
        seen_final.add(s['name'])

with open("botanical_index.json", "w", encoding="utf-8") as f:
    json.dump({"species": final_unique_species}, f, ensure_ascii=False, indent=2)

print(f"Total extracted: {len(final_unique_species)} species.")
