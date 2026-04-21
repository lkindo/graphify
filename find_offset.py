from pypdf import PdfReader

PDF_PATH = r"d:/project/graphify/pdf/koreantree.pdf"
reader = PdfReader(PDF_PATH)

print("--- PDF Physical Page Analysis ---")
for i in [11, 13, 17, 19, 21, 23, 25]: # Physical 12, 14, 18, 20...
    try:
        text = reader.pages[i].extract_text()
        # Print first bit of text to see what's there
        # Since it's garbled, we might see the Scientific Name which is usually cleaner
        print(f"Physical Page {i+1}: raw text preview -> {repr(text[:200])}")
    except:
        print(f"Physical Page {i+1}: Read Error")
