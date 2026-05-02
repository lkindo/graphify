import pypdf
import sys

sys.stdout.reconfigure(encoding='utf-8')

def check_headers(pdf_path, start, end):
    reader = pypdf.PdfReader(pdf_path)
    for i in range(start-1, end):
        text = reader.pages[i].extract_text()
        if text:
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if lines:
                print(f"Page {i+1}: {lines[0]}")
            else:
                print(f"Page {i+1}: NO TEXT")
        else:
            print(f"Page {i+1}: EMPTY")

check_headers("d:/project/graphify/pdf/koreantree1.pdf", 21, 50)
