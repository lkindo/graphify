import fitz

def check_last_pages():
    doc = fitz.open("pdf/flower.pdf")
    with open("flower_last_pages.txt", "w", encoding="utf-8") as f:
        for i in range(len(doc)-10, len(doc)):
            f.write(f"=== Page {i+1} ===\n")
            f.write(doc[i].get_text())
            f.write("\n\n")

if __name__ == "__main__":
    check_last_pages()
