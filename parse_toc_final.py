import json
import re
import os

def parse_toc(file_path):
    with open(file_path, 'rb') as f:
        content = f.read().decode('utf-8', errors='ignore')
    
    lines = content.split('\n')
    
    # Structure: Book -> Large -> Middle -> Small -> Detailed
    # We will approximate this based on the patterns seen
    
    structure = {
        "title": "한국의 나무 (Korean Trees)",
        "categories": []
    }
    
    current_middle = None
    
    # Patterns
    # Family (Middle): Usually ends with '과' like '꿀풀과', '운향과'
    # Species (Detailed): Name followed by dots and page number like '참싸리 . . . . . 168'
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Family detection
        if line.endswith('과') and len(line) < 15:
            current_middle = {
                "name": line,
                "species": []
            }
            structure["categories"].append(current_middle)
        
        # Species detection
        match = re.search(r'(.+?)\s?[\.\s]{3,}(\d+)', line)
        if match:
            name = match.group(1).strip()
            page = match.group(2).strip()
            
            if current_middle is not None:
                current_middle["species"].append({
                    "name": name,
                    "page": page,
                    "description": f"{name}에 대한 상세 설명입니다." # Placeholder for now
                })
    
    return structure

if __name__ == '__main__':
    data = parse_toc('extracted_toc_raw.txt')
    with open('botanical_structure.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Successfully parsed {len(data['categories'])} families.")
