import pypdf
import re
import json

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
toc_data = {}

for i in [3, 4, 5]: # Pages 4, 5, 6
    text = reader.pages[i].extract_text()
    if text:
        nums = re.findall(r'\d{1,3}', text)
        for n in nums:
            p = int(n)
            if 9 <= p <= 409:
                toc_data[p] = ""

for p in toc_data.keys():
    if p + 1 < len(reader.pages):
        name = get_header(reader.pages[p + 1])
        if name:
            toc_data[p] = name

with open('toc_list.md', 'w', encoding='utf-8') as f:
    f.write("| 나무명 | 페이지 |\n")
    f.write("|---|---|\n")
    sorted_toc = sorted(toc_data.items())
    for p, name in sorted_toc:
        display_name = name if name else "(이름 확인 불가)"
        f.write(f"| {display_name} | {p} |\n")
