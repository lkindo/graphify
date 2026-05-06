import pypdf
import re

TOC_SAMPLES = {
    8: "소철",
    50: "자주받침꽃",
    100: "개머루",
    150: "다릅나무",
    200: "갯대추나무",
    250: "배롱나무",
    300: "층층나무",
    350: "개오동",
    400: "송악"
}

def clean_korean(text):
    if not text: return ""
    return "".join(re.findall(r'[가-힣]+', text))

def find_pdf_page(reader, species_name, start_pdf_page):
    # Search within +/- 10 pages of start_pdf_page
    for p_num in range(max(1, start_pdf_page - 10), min(len(reader.pages), start_pdf_page + 15)):
        text = reader.pages[p_num - 1].extract_text()
        if species_name in clean_korean(text):
            return p_num
    return None

reader = pypdf.PdfReader('pdf/tree.pdf')
offsets = {}

print("| Book Page | Species | PDF Page | Offset |")
print("|---|---|---|---|")

for bp, name in sorted(TOC_SAMPLES.items()):
    # Expected PDF page is bp + 1 (if offset is 1)
    pdf_p = find_pdf_page(reader, name, bp + 1)
    if pdf_p:
        offset = pdf_p - bp
        offsets[bp] = offset
        print(f"| {bp} | {name} | {pdf_p} | {offset} |")
    else:
        print(f"| {bp} | {name} | NOT FOUND | - |")
