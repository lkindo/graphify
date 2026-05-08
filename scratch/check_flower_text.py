import fitz

def list_first_pages_text():
    doc = fitz.open("pdf/flower.pdf")
    with open("flower_pages_text.txt", "w", encoding="utf-8") as f:
        for i in range(min(len(doc), 20)):
            f.write(f"=== Page {i+1} ===\n")
            f.write(doc[i].get_text())
            f.write("\n\n")

if __name__ == "__main__":
    list_first_pages_text()
