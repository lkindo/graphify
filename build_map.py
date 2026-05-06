import pypdf
import re
import json

def get_bpn(text):
    if not text: return None
    # Look for numbers in the range 1-450
    # Usually the page number is at the very end or very beginning of the text
    lines = text.splitlines()
    if not lines: return None
    
    # Check last 5 lines for a number
    for line in reversed(lines[-5:]):
        nums = re.findall(r'\b(\d{1,3})\b', line)
        if nums:
            # Take the one closest to the end of the line
            for n in reversed(nums):
                val = int(n)
                if 1 <= val <= 450:
                    return val
    
    # Check first 5 lines
    for line in lines[:5]:
        nums = re.findall(r'\b(\d{1,3})\b', line)
        if nums:
            for n in nums:
                val = int(n)
                if 1 <= val <= 450:
                    return val
    return None

reader = pypdf.PdfReader('pdf/tree.pdf')
pdf_to_bpn = {}

print("Scanning PDF pages for book page numbers...")
for i in range(len(reader.pages)):
    text = reader.pages[i].extract_text()
    bpn = get_bpn(text)
    if bpn:
        pdf_to_bpn[i + 1] = bpn
        print(f"PDF Page {i+1} -> Book Page {bpn}")

with open('pdf_page_map.json', 'w') as f:
    json.dump(pdf_to_bpn, f)

print(f"Mapping complete. Found {len(pdf_to_bpn)} anchors.")
