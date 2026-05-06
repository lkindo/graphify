import pypdf
import re

def clean_korean(text):
    if not text: return ""
    return "".join(re.findall(r'[가-힣]+', text))

def get_header(page_obj):
    text = page_obj.extract_text()
    if not text: return ""
    lines = text.splitlines()
    if not lines: return ""
    for line in lines[:3]:
        name = clean_korean(line)
        if 2 <= len(name) <= 12:
            return name
    return ""

reader = pypdf.PdfReader('pdf/tree.pdf')
p_nums = set()
for i in [3, 4, 5]:
    text = reader.pages[i].extract_text()
    if text:
        p_nums.update(re.findall(r'\d{1,3}', text))

sorted_p = sorted([int(n) for n in p_nums if 9 <= int(n) <= 409])

with open('species_list.md', 'w', encoding='utf-8') as f:
    f.write("| 페이지 | 나무 이름 |\n")
    f.write("|---|---|\n")
    for p in sorted_p:
        name = ""
        if p + 1 < len(reader.pages):
            name = get_header(reader.pages[p + 1])
        
        if not name:
            name = "(이름 확인 불가)"
            
        f.write(f"| {p} | {name} |\n")
