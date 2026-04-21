import json
import re

def parse_full_toc(file_path):
    with open(file_path, 'rb') as f:
        content = f.read().decode('utf-8', errors='ignore')
    
    # Split by pages to keep context
    pages = content.split('--- Page')
    
    structure = {
        "book": "한국의 나무 (Korean Trees)",
        "large_categories": [
            {
                "name": "일반 수종 (General Species)",
                "middle_categories": []
            }
        ]
    }
    
    current_middle = None
    current_small = None
    
    # Regex for Family (Middle): ends with '과'
    family_pattern = re.compile(r'^([가-힣]+과)$')
    # Regex for Species: Name + Scientific (Latin) + Page
    # Example: '참싸리 Lespedeza cyrtobotrya . 70'
    species_pattern = re.compile(r'([가-힣\s/]+)\s?([A-Za-z\.\s]+)\s?[\.\s]{2,}(\d+)')

    for page_content in pages:
        lines = page_content.split('\n')
        for line in lines:
            line = line.strip()
            if not line or 'Page' in line or '수록종' in line or '차례' in line:
                continue
            
            # 1. Detect Middle Category (Family)
            if family_pattern.match(line):
                family_name = family_pattern.match(line).group(1)
                current_middle = {
                    "name": family_name,
                    "small_categories": []
                }
                structure["large_categories"][0]["middle_categories"].append(current_middle)
                current_small = None # Reset small category
                continue
            
            # 2. Detect Species (Detailed)
            match = species_pattern.search(line)
            if match:
                name = match.group(1).strip()
                sci_name = match.group(2).strip()
                page = match.group(3).strip()
                
                # Logic to guess "Small Category" (Genus) from scientific name's first word
                genus = sci_name.split(' ')[0] if sci_name else "기타"
                
                if current_middle:
                    # Find or create small category
                    if not current_small or current_small["name"].startswith(genus) == False:
                        current_small = {
                            "name": f"{genus} 속",
                            "species": []
                        }
                        current_middle["small_categories"].append(current_small)
                    
                    current_small["species"].append({
                        "name": name,
                        "scientific_name": sci_name,
                        "page": page,
                        "summary": f"{name}에 대한 기초 정보를 수집 중입니다.",
                        "details": {}
                    })
    
    return structure

if __name__ == '__main__':
    data = parse_full_toc('extracted_toc_raw.txt')
    with open('botanical_structure_full.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Summary stats
    m_count = len(data["large_categories"][0]["middle_categories"])
    s_count = sum(len(m["small_categories"]) for m in data["large_categories"][0]["middle_categories"])
    sp_count = sum(len(s["species"]) for m in data["large_categories"][0]["middle_categories"] for s in m["small_categories"])
    print(f"Parsed: {m_count} Families, {s_count} Genera, {sp_count} Species.")
