import pypdf
import json
import re
import os

def extract_toc(pdf_path):
    reader = pypdf.PdfReader(pdf_path)
    all_species = []
    
    # Normally TOC is roughly pages 6 to 25
    for i in range(5, 25):  
        page = reader.pages[i]
        text = page.extract_text()
        if not text: continue
        
        # Regex to match Name ... Page
        # We handle variations like dots, spaces, etc.
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            # Look for plant name followed by botanical name and page number
            # Example: 참싸리 Lespedeza cyrtobotrya . 70
            match = re.search(r'([가-힣\s\-\(\)\.]+)\s+([A-Za-z\s\.\-x\(\)]+)\s+[\.\s]*(\d+)', line)
            if match:
                name = match.group(1).strip()
                sci_name = match.group(2).strip()
                page_num = match.group(3)
                
                # Check for duplications
                if any(s["name"] == name for s in all_species):
                    continue
                    
                all_species.append({
                    "name": name,
                    "scientific_name": sci_name,
                    "page": page_num,
                    "summary": f"PDF {page_num}페이지에서 추출한 {name}의 생태 정보입니다.",
                    "details": {
                        "distribution": "시스템 추출 중...",
                        "form": "시스템 추출 중...",
                        "leaves": "시스템 추출 중...",
                        "flowers": "시스템 추출 중...",
                        "fruits": "시스템 추출 중..."
                    }
                })
    return all_species

if __name__ == "__main__":
    pdf_path = "d:/project/graphify/pdf/koreantree.pdf"
    species_list = extract_toc(pdf_path)
    
    # Filter out TOC-like labels that aren't actually species if needed
    
    data = {
        "book": "한국의 나무 (Korean Trees)",
        "large_categories": [
            {
                "name": "전체 수종 (Total Species)",
                "middle_categories": [
                    {
                        "name": f"자동 추출된 {len(species_list)}종",
                        "small_categories": [
                            {
                                "name": "식물 목록",
                                "species": species_list
                            }
                        ]
                    }
                ]
            }
        ]
    }
    
    out_path = "d:/project/graphify/botanical_structure.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"COMPLETE: {len(species_list)} species extracted.")
