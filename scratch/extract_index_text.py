import fitz

def extract_index_text():
    doc = fitz.open("pdf/index.pdf")
    with open("index_pdf_text.txt", "w", encoding="utf-8") as f:
        for i in range(len(doc)):
            f.write(f"=== Page {i+1} ===\n")
            f.write(doc[i].get_text())
            f.write("\n\n")

if __name__ == "__main__":
    extract_index_text()
