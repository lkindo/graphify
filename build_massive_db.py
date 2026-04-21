import json
import re

def build_data():
    try:
        with open('extracted_toc_raw.txt', 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        with open('extracted_toc_raw.txt', 'r', encoding='utf-16le') as f:
            content = f.read()

    # Regex for Family: 'xxx과'
    family_re = re.compile(r'^([가-힣]+과)$')
    # Regex for Species: 'Name Scientific . Page'
    species_re = re.compile(r'^([가-힣\s/]{2,})\s+([A-Z][a-z]+[\sA-Za-z\.\s]*)\s+[\.\s]+(\d+)$')

    data = {
        "book": "한국의 나무 (Korean Trees)",
        "large_categories": [
            {
                "name": "일반 수종 (General Species)",
                "middle_categories": []
            }
        ]
    }

    current_family = None
    current_genus_name = None
    current_genus_obj = None

    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Family detection
        fam_match = family_re.match(line)
        if fam_match:
            current_family = {
                "name": fam_match.group(1),
                "small_categories": []
            }
            data["large_categories"][0]["middle_categories"].append(current_family)
            current_genus_name = None
            continue
        
        # Species detection
        sp_match = species_re.match(line)
        if sp_match and current_family:
            name = sp_match.group(1).strip()
            sci = sp_match.group(2).strip()
            page = sp_match.group(3).strip()
            
            genus = sci.split(' ')[0]
            if genus != current_genus_name:
                current_genus_name = genus
                current_genus_obj = {
                    "name": genus + "속",
                    "species": []
                }
                current_family["small_categories"].append(current_genus_obj)
            
            current_genus_obj["species"].append({
                "name": name,
                "scientific_name": sci,
                "page": page,
                "summary": f"{name}에 대한 식생 정보를 PDF {page}페이지에서 확인할 수 있습니다."
            })

    # Add detailed sample for validation
    for fam in data["large_categories"][0]["middle_categories"]:
        if fam["name"] == "콩과":
            for genus in fam["small_categories"]:
                for sp in genus["species"]:
                    if sp["name"] == "참싸리":
                        sp["summary"] = "산지의 볕이 잘 드는 곳에서 자라는 낙엽 활엽 관목입니다."
                        sp["details"] = {
                            "distribution": "한국, 일본, 중국, 러시아",
                            "form": "낙엽 활엽 관목, 높이 2m 내외",
                            "leaves": "3출엽, 어긋나기, 소엽은 도란형",
                            "flowers": "7~9월 홍자색 개화, 짧은 총상꽃차례",
                            "fruits": "협과, 달걀 모양 타원형, 9~11월 성숙"
                        }
                        sp["image"] = "korean_tree_lespedeza_1776749307995.png"

    with open('botanical_structure.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Total Families: {len(data['large_categories'][0]['middle_categories'])}")

if __name__ == "__main__":
    build_data()
