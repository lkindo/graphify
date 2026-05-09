import fitz  # PyMuPDF
import os

def extract_images():
    md_path = 'species_verification.md'
    pdf_path = 'pdf/flower.pdf'
    output_dir = 'assets/wtrees'
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 1. Read names from MD
    species_list = []
    with open(md_path, 'r', encoding='utf-8') as f:
        for line in f:
            name = line.strip()
            if name:
                species_list.append(name)
    
    print(f'Total species: {len(species_list)}')
    
    # 2. Open PDF
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f'Total PDF pages: {total_pages}')
    
    # 3. Extract by rendering page
    for i, name in enumerate(species_list):
        page_num = i + 1
        if page_num > total_pages:
            print(f'[{page_num}] Warning: Exceeds PDF pages. Skipping.')
            break
            
        page = doc.load_page(page_num - 1)
        
        # Render page as image (2x zoom for good quality)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        
        filename = f'{name}.jpg'
        filepath = os.path.join(output_dir, filename)
        
        pix.save(filepath)
        print(f'[{page_num}] Saved {name} -> {filename}')
            
    doc.close()

if __name__ == "__main__":
    extract_images()
