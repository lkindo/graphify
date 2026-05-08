import pypdf
import sys

def probe():
    reader = pypdf.PdfReader('pdf/flower.pdf')
    with open('pdf_probe.txt', 'w', encoding='utf-8') as f:
        for i in range(10):
            f.write(f"--- Page {i+1} ---\n")
            text = reader.pages[i].extract_text()
            f.write(text if text else "NO TEXT")
            f.write("\n\n")

if __name__ == "__main__":
    probe()
