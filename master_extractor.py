import pypdf
import os
import shutil
import json
import re

# Full TOC Mapping (Book Page -> Name)
TOC = {
    8: "소철", 10: "은행나무", 12: "전나무", 14: "구상나무", 16: "솔송나무", 18: "독일가문비", 20: "잣나무", 22: "소나무",
    26: "일본잎갈나무", 28: "개잎갈나무", 30: "메타세쿼이아", 32: "삼나무", 34: "측백나무", 36: "편백", 38: "향나무",
    40: "비자나무", 42: "주목", 44: "오미자", 46: "붓순나무", 48: "등칡", 50: "자주받침꽃", 52: "생강나무", 54: "비목나무",
    56: "녹나무", 58: "후박나무", 60: "백목련", 62: "함박꽃나무", 64: "일본목련", 66: "태산목", 68: "튤립나무",
    70: "청미래덩굴", 72: "종려나무", 76: "매발톱나무", 78: "으름덩굴", 80: "멀꿀", 82: "종덩굴",
    84: "양버즘나무", 86: "회양목", 88: "계수나무", 90: "굴거리", 92: "까마귀밥여름나무", 94: "조록나무", 96: "히어리",
    98: "모란", 100: "개머루", 102: "담쟁이덩굴", 104: "사철나무", 106: "화살나무", 110: "회나무", 112: "노박덩굴",
    114: "예덕나무", 116: "사람주나무", 118: "유동", 120: "망종화", 122: "이나무", 124: "은사시나무", 128: "버드나무",
    130: "갯버들", 132: "자귀나무", 134: "박태기나무", 136: "칡", 138: "골담초", 140: "아까시나무", 142: "등",
    144: "족제비싸리", 146: "싸리", 148: "회화나무", 150: "다릅나무", 152: "오리나무", 154: "사방오리", 156: "박달나무",
    158: "자작나무", 162: "개암나무", 164: "서어나무", 166: "밤나무", 168: "구실잣밤나무", 170: "상수리나무", 174: "가시나무",
    176: "굴피나무", 178: "중국굴피나무", 180: "가래나무", 182: "소귀나무", 184: "팽나무", 186: "보리수나무", 188: "꾸지뽕나무",
    190: "닥나무", 192: "산뽕나무", 194: "천선과나무", 196: "무화과", 198: "대추나무", 200: "갯대추나무", 202: "가침박달",
    204: "조팝나무", 208: "국수나무", 210: "매실나무", 212: "살구나무", 214: "복숭아나무", 216: "왕벚나무", 218: "앵두나무",
    220: "찔레꽃", 222: "해당화", 224: "산딸기", 228: "황매화", 230: "비파나무", 232: "다정큼나무", 234: "모과나무",
    236: "사과나무", 238: "산사나무", 240: "콩배나무", 242: "마가목", 244: "팥배나무", 246: "느릅나무", 248: "느티나무",
    250: "배롱나무", 252: "석류나무", 254: "벽오동", 256: "장구밥나무", 258: "피나무", 260: "무궁화", 262: "삼지닥나무",
    264: "붉나무", 266: "개옻나무", 268: "초피나무", 270: "산초나무", 272: "쉬나무", 274: "황벽나무", 276: "탱자나무",
    278: "유자나무", 280: "귤", 282: "고로쇠나무", 284: "단풍나무", 290: "가죽나무", 292: "소태나무", 294: "겨우살이",
    296: "산딸나무", 298: "산수유", 300: "층층나무", 304: "물참대", 306: "수국", 308: "산수국", 310: "다래", 314: "개다래",
    316: "감나무", 318: "철쭉", 320: "진달래", 322: "정금나무", 324: "사스레피나무", 326: "자금우", 328: "때죽나무",
    330: "쪽동백나무", 332: "노린재나무", 334: "동백나무", 336: "노각나무", 338: "산다화", 340: "마삭줄", 342: "치자나무",
    344: "구슬꽃나무", 346: "계요등", 348: "능소화", 350: "개오동", 352: "작살나무", 354: "층꽃나무", 356: "누리장나무",
    358: "순비기나무", 360: "물푸레나무", 362: "들메나무", 364: "미선나무", 366: "개나리", 370: "라일락", 372: "이팝나무",
    374: "쥐똥나무", 376: "참오동", 378: "구기자나무", 380: "먼나무", 382: "호랑가시나무", 384: "광나무", 386: "딱총나무",
    388: "가막살나무", 390: "분꽃나무", 392: "인동덩굴", 394: "댕강나무", 396: "백당나무", 398: "괴불나무", 400: "송악",
    402: "팔손이", 404: "황칠나무", 406: "오갈피나무", 408: "돈나무"
}

# Manual PDF Page Overrides (Book Page -> (PDF Page 1, PDF Page 2))
MANUAL_OVERRIDES = {
    8: (9, 10),     # 소철
    76: (77, 78),   # 매발톱나무
    128: (129, 130), # 버드나무
    130: (131, 132), # 갯버들
    144: (145, 146), # 족제비싸리
    146: (147, 148), # 싸리
    296: (297, 300), # 산딸나무 (Visual Verified: PDF 297, 300)
    298: (301, 302), # 산수유 (Visual Verified: PDF 301, 302)
    300: (303, 304)  # 층층나무 (Visual Verified: PDF 303, 304)
}

def clean_korean(text):
    if not text: return ""
    return "".join(re.findall(r'[가-힣]+', text))

def extract_accurate_v2():
    pdf_path = "pdf/tree.pdf"
    output_dir = "assets/trees"
    
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    reader = pypdf.PdfReader(pdf_path)
    all_species_data = []
    
    current_pdf_page = 1
    sorted_bpns = sorted(TOC.keys())
    total = len(sorted_bpns)
    
    print("Starting Corrected Accurate Extraction...")
    
    for idx, bp in enumerate(sorted_bpns):
        name = TOC[bp]
        found_p1 = None
        
        # 1. Check for manual override
        if bp in MANUAL_OVERRIDES:
            p1, p2 = MANUAL_OVERRIDES[bp]
            print(f"  [{idx+1}/{total}] {name}: Using MANUAL OVERRIDE (PDF {p1}, {p2})")
            found_p1 = p1
        else:
            # 2. Sequential Header Search
            search_start = current_pdf_page
            search_end = min(len(reader.pages), bp + 50)
            
            for p_idx in range(search_start, search_end + 1):
                text = reader.pages[p_idx - 1].extract_text()
                if not text: continue
                
                header = clean_korean(" ".join(text.splitlines()[:3]))
                if name in header:
                    print(f"  [{idx+1}/{total}] {name}: FOUND at PDF Page {p_idx}")
                    found_p1 = p_idx
                    break
        
        if found_p1:
            p1 = found_p1
            p2 = p1 + 1 # Rule: Next page is always Image 2
            
            # Special case for manual overrides that specify p1, p2
            if bp in MANUAL_OVERRIDES:
                p1, p2 = MANUAL_OVERRIDES[bp]
            
            extracted_files = []
            for img_idx, p_num in enumerate([p1, p2]):
                if p_num > len(reader.pages): continue
                p_obj = reader.pages[p_num - 1]
                if '/Resources' in p_obj and '/XObject' in p_obj['/Resources']:
                    xObject = p_obj['/Resources']['/XObject'].get_object()
                    img_objs = []
                    for obj in xObject:
                        if xObject[obj]['/Subtype'] == '/Image':
                            try:
                                data = xObject[obj].get_data()
                                img_objs.append((len(data), data))
                            except: continue
                    if img_objs:
                        img_objs.sort(key=lambda x: x[0], reverse=True)
                        data = img_objs[0][1]
                        fname = f"{name}_{img_idx + 1}.jpg"
                        with open(os.path.join(output_dir, fname), "wb") as f:
                            f.write(data)
                        extracted_files.append(fname)
            
            if extracted_files:
                all_species_data.append({
                    "name": name,
                    "category": "한국의 나무",
                    "images": [f"assets/trees/{f}" for f in extracted_files],
                    "summary": f"{name}에 대한 도감 정보입니다.",
                    "details": f"{name}의 사진입니다. (PDF Pages {p1}-{p2})"
                })
            
            current_pdf_page = p2 + 1
        else:
            print(f"  [{idx+1}/{total}] WARNING: {name} NOT FOUND. Skipping.")

    with open("botanical_index.json", "w", encoding="utf-8") as f:
        json.dump({"species": all_species_data}, f, ensure_ascii=False, indent=2)
    
    print(f"Complete! Total {len(all_species_data)} species extracted.")

if __name__ == "__main__":
    extract_accurate_v2()
