import re
import json

def parse_toc(filename):
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    structure = {
        'title': '한국의 나무',
        'categories': []
    }
    
    current_family = None
    current_category = {
        'name': '일반 수종',
        'families': []
    }
    structure['categories'].append(current_category)
    
    # Family pattern: ends with '과'
    family_pattern = re.compile(r'^([가-힣]+과)\s*$')
    # Species pattern: Name, Scientific Name, dots, Page
    # Example: 섬백리향 Thymusquin... 6
    species_pattern = re.compile(r'^([가-힣]+)\s+([A-Za-z.\s]+)\s*(?:(?:\.+|\s+))(\d+)')

    for line in lines:
        line = line.strip()
        fam_match = family_pattern.match(line)
        if fam_match:
            current_family = {
                'family_name': fam_match.group(1),
                'species': []
            }
            current_category['families'].append(current_family)
            continue
        
        spec_match = species_pattern.match(line)
        if spec_match and current_family is not None:
            current_family['species'].append({
                'name': spec_match.group(1),
                'scientific_name': spec_match.group(2).strip(),
                'page': int(spec_match.group(3))
            })

    return structure

if __name__ == '__main__':
    data = parse_toc('extracted_toc_raw.txt')
    with open('botanical_structure.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Successfully parsed {sum(len(fam['species']) for cat in data['categories'] for fam in cat['families'])} species.")
