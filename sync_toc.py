import json
import re

def parse_full_toc(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # regex for "Group Name (Optionally numbers) KoreanName ScientificName ... Page"
    # Example: 618 능소화Campsis grandiflora • 28
    # Example: 참싸리 Lespedeza cyrtobotrya . 70
    
    species_list = []
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        # Pattern 1: ID Name ScientificName Page
        match = re.search(r'(?:\d+\s+)?([가-힣]+)\s*([A-Za-z\s\.\-x\(\)]+)\s*[\.\s•]*(\d+)', line)
        if match:
            korean_name = match.group(1).strip()
            sci_name = match.group(2).strip()
            page = match.group(3)
            
            # Filter valid botanical names (usually start with uppercase)
            if not sci_name or not re.match(r'[A-Z]', sci_name):
                # Maybe the scientific name and korean name are reversed or scientific name is missing
                continue
                
            species_list.append({
                "name": korean_name,
                "scientific_name": sci_name,
                "page": page,
                "summary": f"PDF {page}페이지에 있는 {korean_name}의 상세 정보입니다.",
                "details": {
                    "distribution": "추출 대기 중",
                    "form": "추출 대기 중",
                    "leaves": "추출 대기 중",
                    "flowers": "추출 대기 중",
                    "fruits": "추출 대기 중"
                }
            })
            
    # Category sorting (simplifying for now to show the user the count)
    data = {
        "book": "한국의 나무 (Korean Trees)",
        "total_count": len(species_list),
        "large_categories": [
            {
                "name": "전체 수종",
                "middle_categories": [
                    {
                        "name": f"검색된 {len(species_list)}종",
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
    return data

if __name__ == "__main__":
    result = parse_full_toc("d:/project/graphify/full_toc_text.txt")
    with open("d:/project/graphify/botanical_structure.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"DONE: {result['total_count']} species imported.")
