import os
import sys
from pypdf import PdfReader

# Ensure UTF-8 output for terminal
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

pdf_path = r"d:/project/graphify/pdf/koreantree.pdf"
output_dir = r"d:/project/graphify/assets/species"

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

targets = [
    {"name": "능소화", "page": 40},
    {"name": "참싸리", "page": 82},
    {"name": "조록싸리", "page": 90}
]

reader = PdfReader(pdf_path)

for target in targets:
    try:
        page_idx = target["page"] - 1
        page = reader.pages[page_idx]
        
        found = False
        for i, image_file_object in enumerate(page.images):
            # We skip tiny icons if any (usually smaller than 10KB)
            if len(image_file_object.data) < 10240:
                continue
                
            img_name = f"{target['name']}.png"
            full_path = os.path.join(output_dir, img_name)
            
            with open(full_path, "wb") as fp:
                fp.write(image_file_object.data)
            print(f"Successfully extracted: {img_name} ({len(image_file_object.data)} bytes)")
            found = True
            break # Get only the first substantial image
            
        if not found:
            print(f"No substantial image found on page {target['page']} for {target['name']}")
            
    except Exception as e:
        print(f"Error processing {target['name']}: {str(e)}")
