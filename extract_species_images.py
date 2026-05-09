import pypdf
import os
from collections import defaultdict

def extract_images():
    md_path = 'species_verification.md'
    pdf_path = 'pdf/flower.pdf'
    output_dir = 'assets/leaves'
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 1. Read names from MD
    species_list = []
    with open(md_path, 'r', encoding='utf-8') as f:
        for line in f:
            name = line.strip()
            if name:
                species_list.append(name)
    
    print(f'Total species to extract: {len(species_list)}')
    
    # 2. Open PDF
    reader = pypdf.PdfReader(pdf_path)
    total_pages = len(reader.pages)
    print(f'Total PDF pages: {total_pages}')
    
    # 3. Extract
    for i, name in enumerate(species_list):
        page_num = i + 1
        if page_num > total_pages:
            print(f'Warning: Page {page_num} exceeds PDF total pages. Skipping.')
            break
        
        page = reader.pages[page_num - 1]
        
        if '/Resources' in page and '/XObject' in page['/Resources']:
            xObject = page['/Resources']['/XObject'].get_object()
            img_objs = []
            for obj in xObject:
                if xObject[obj]['/Subtype'] == '/Image':
                    try:
                        data = xObject[obj].get_data()
                        img_objs.append((len(data), data, xObject[obj].get('/Filter')))
                    except Exception as e:
                        print(f'Error extracting image on page {page_num}: {e}')
                        continue
            
            if img_objs:
                # Sort by size to get the main image
                img_objs.sort(key=lambda x: x[0], reverse=True)
                size, data, img_filter = img_objs[0]
                
                # Determine extension
                ext = 'jpg'
                if img_filter == '/FlateDecode':
                    ext = 'png'
                elif img_filter == '/JPXDecode':
                    ext = 'jp2'
                
                # Use only the name for the filename
                filename = f'{name}.{ext}'
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(data)
                print(f'[{page_num}] Extracted {name} -> {filename} ({size} bytes)')
            else:
                print(f'[{page_num}] No images found for {name}')
        else:
            print(f'[{page_num}] No resources found for {name}')

if __name__ == "__main__":
    extract_images()
