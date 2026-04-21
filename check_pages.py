import sys
import io
from pypdf import PdfReader

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

pdf_path = r"d:/project/graphify/pdf/koreantree.pdf"
reader = PdfReader(pdf_path)

# Scan pages 30 to 150 to find key species
for i in range(25, 100):
    text = reader.pages[i].extract_text()
    if "참싸리" in text:
        print(f"FOUND: 참싸리 at Physical Page {i+1}")
    if "능소화" in text:
        print(f"FOUND: 능소화 at Physical Page {i+1}")
    if "조록싸리" in text:
        print(f"FOUND: 조록싸리 at Physical Page {i+1}")
