import fitz
import os

def extract_all_pages_by_number():
    pdf_path = r'd:\project\graphify\pdf\tree.pdf'
    output_dir = r'd:\project\graphify\debug_pages'
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    doc = fitz.open(pdf_path)
    for i in range(8, 412): # 9p to 412p (0-indexed 8 to 411)
        if i >= len(doc): break
        
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(1, 1))
        # Save as 0-indexed page number for absolute accuracy
        pix.save(os.path.join(output_dir, f"page_{i:03d}.jpg"))
    
    doc.close()
    print(f"Extracted {412-8} pages to debug_pages folder.")

if __name__ == "__main__":
    extract_all_pages_by_number()
