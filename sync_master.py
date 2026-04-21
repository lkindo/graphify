import pypdf
import json
import os
import re

PDF_PATH = "d:/project/graphify/pdf/koreantree.pdf"
JSON_PATH = "d:/project/graphify/botanical_structure.json"
TOC_PATH = "d:/project/graphify/full_toc_text.txt"
ASSET_DIR = "d:/project/graphify/assets/species"
os.makedirs(ASSET_DIR, exist_ok=True)

def build_full_data():
    if not os.path.exists(TOC_PATH):
        print("TOC file not found.")
        return

    with open(TOC_PATH, "r", encoding="utf-8") as f:
        toc_text = f.read()

    # Regex to capture name, scientific name, and page
    # Matches: 가시칠엽수 Aesculus turbinata 21
    pattern = re.compile(r"([가-힣]+)\s+([A-Z][a-z\.\s]+)\s+(\d+)")
    matches = pattern.findall(toc_text)
    
    print(f"Found {len(matches)} species in TOC.")
    
    species_list = []
    reader = pypdf.PdfReader(PDF_PATH)
    offset = 12

    for name, sci_name, page_str in matches:
        logical_page = int(page_str)
        physical_page = logical_page + offset
        
        species_entry = {
            "name": name,
            "scientific_name": sci_name.strip(),
            "page": logical_page,
            "image": "",
            "summary": f"{name}에 대한 정보입니다.",
            "details": {
                "distribution": "정보 수집 중...",
                "form": "본문 내용을 분석 중입니다."
            }
        }
        
        # Extract metadata if possible
        if physical_page < len(reader.pages):
            page = reader.pages[physical_page]
            text = page.extract_text()
            
            # Simple metadata extraction
            species_entry["details"]["form"] = text[:500].replace("\n", " ")
            
            # Extract Image
            if len(page.images) > 0:
                try:
                    img_data = page.images[0].data
                    img_filename = f"{name}.png"
                    with open(os.path.join(ASSET_DIR, img_filename), "wb") as fimg:
                        fimg.write(img_data)
                    species_entry["image"] = f"assets/species/{img_filename}"
                except:
                    pass
        
        species_list.append(species_entry)

    data = {
        "book": "한국의 나무",
        "total_count": len(species_list),
        "large_categories": [
            {
                "name": "전체 수종",
                "middle_categories": [
                    {
                        "name": "식물 목록",
                        "small_categories": [
                            {
                                "name": "주요 수종",
                                "species": species_list
                            }
                        ]
                    }
                ]
            }
        ]
    }

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Master JSON built with {len(species_list)} species.")

if __name__ == "__main__":
    build_full_data()
