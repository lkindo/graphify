from pypdf import PdfReader
import sys

def extract_page_text(pdf_path, page_num):
    try:
        reader = PdfReader(pdf_path)
        page = reader.pages[page_num - 1] # 0-indexed
        text = page.extract_text()
        return text
    except Exception as e:
        return str(e)

if __name__ == '__main__':
    # Page 70 is 참싸리 according to TOC
    result = extract_page_text('pdf/koreantree.pdf', 70)
    sys.stdout.reconfigure(encoding='utf-8')
    print(result)
