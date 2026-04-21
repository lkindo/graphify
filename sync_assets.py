import pypdf
import json
import os

PDF_PATH = "d:/project/graphify/pdf/koreantree.pdf"
JSON_PATH = "d:/project/graphify/botanical_structure.json"
ASSET_DIR = "d:/project/graphify/assets/species"
os.makedirs(ASSET_DIR, exist_ok=True)

def sync():
    if not os.path.exists(JSON_PATH):
        print("JSON not found.")
        return

    reader = pypdf.PdfReader(PDF_PATH)
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Locate species list
    species_list = data['large_categories'][0]['middle_categories'][0]['small_categories'][0]['species']
    
    # We use a fixed offset of 12 for the whole book for now.
    # If the user wants precise mapping, we match the name in text.
    offset = 12
    count = 0
    
    for s in species_list:
        name = s['name']
        logical_page = s['page']
        physical_page = logical_page + offset
        
        if physical_page < len(reader.pages):
            page = reader.pages[physical_page]
            text = page.extract_text()
            
            # Verify if name is on this page
            if name not in text:
                # Search nearby
                found = False
                for i in range(max(0, physical_page-5), min(len(reader.pages), physical_page+10)):
                    if name in reader.pages[i].extract_text():
                        page = reader.pages[i]
                        physical_page = i
                        found = True
                        break
            
            # Extract Image
            if len(page.images) > 0:
                try:
                    img_data = page.images[0].data
                    img_filename = f"{name}.png"
                    with open(os.path.join(ASSET_DIR, img_filename), "wb") as fimg:
                        fimg.write(img_data)
                    s['image'] = f"assets/species/{img_filename}"
                except Exception as e:
                    print(f"Error extracting image for {name}: {e}")
            
            # Update Description
            s['details']['form'] = page.extract_text()[:600].replace('\n', ' ')
            count += 1
            if count % 10 == 0:
                print(f"Processed {count} species...")

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Sync complete. Processed {count} species.")

if __name__ == "__main__":
    sync()
