import pypdf
import os
import json

ASSET_DIR = "d:/project/graphify/assets/species"
os.makedirs(ASSET_DIR, exist_ok=True)

def extract_for_species(pdf_path, name, page_num):
    reader = pypdf.PdfReader(pdf_path)
    # The page number in TOC is 'logical'. 
    # From sync_toc results, we see 참싸리 is 70.
    # Let's find the physical page. 
    # Usually, page 1 of book is around physical page 14-16.
    
    physical_page = -1
    # Search nearby for the name
    start = max(10, page_num + 5) # Rough offset
    end = min(len(reader.pages), page_num + 30)
    
    for i in range(start, end):
        text = reader.pages[i].extract_text()
        if name in text:
            physical_page = i
            break
            
    if physical_page == -1:
        return f"Could not find {name} near page {page_num}"

    page = reader.pages[physical_page]
    
    # Save the first image found on this page
    img_path = ""
    if len(page.images) > 0:
        img_obj = page.images[0]
        ext = img_obj.name.split('.')[-1] if '.' in img_obj.name else 'png'
        filename = f"{name}.{ext}"
        full_path = os.path.join(ASSET_DIR, filename)
        with open(full_path, "wb") as f:
            f.write(img_obj.data)
        img_path = f"assets/species/{filename}"
    
    desc = page.extract_text().strip()
    return {
        "name": name,
        "image": img_path,
        "description": desc[:500] + "..." # Truncate for JSON
    }

if __name__ == "__main__":
    pdf = "d:/project/graphify/pdf/koreantree.pdf"
    targets = [
        ("참싸리", 70),
        ("능소화", 28),
        ("조록싸리", 78)
    ]
    
    results = []
    for n, p in targets:
        results.append(extract_for_species(pdf, n, p))
        
    with open("d:/project/graphify/extracted_fixed.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("Extraction complete.")
