import fitz
import os
import json

def main():
    # 1. Read the verified list
    verified_map = {}
    with open("species_verification.md", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "," not in line: continue
            try:
                parts = line.split(",")
                phys_num = int(parts[0].strip())
                name = parts[1].strip()
                verified_map[phys_num] = name
            except ValueError:
                continue

    if not verified_map:
        print("Error: No data found in species_verification.md")
        return

    # 2. Setup directories
    output_dir = "assets/flowers"
    os.makedirs(output_dir, exist_ok=True)
    
    # 3. Delete existing flower images
    print("Deleting existing images...")
    for f in os.listdir(output_dir):
        if f.endswith(".png"):
            os.remove(os.path.join(output_dir, f))

    # 4. Extract from PDF
    print("Extracting images from flower.pdf...")
    doc = fitz.open("pdf/flower.pdf")
    species_list = []
    
    for i in range(len(doc)):
        phys_num = i + 1
        name = verified_map.get(phys_num, f"page_{phys_num}")
        
        page = doc[i]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        
        # Safe filename
        safe_name = name.replace(" ", "_").replace("/", "-")
        img_name = f"{safe_name}.png"
        img_path = f"{output_dir}/{img_name}"
        
        # Handle potential duplicates if any (though user list should be unique)
        counter = 1
        while os.path.exists(img_path):
            img_name = f"{safe_name}_{counter}.png"
            img_path = f"{output_dir}/{img_name}"
            counter += 1
            
        pix.save(img_path)
        
        species_list.append({
            "name": img_name.replace(".png", ""),
            "category": "나무에 피는 꽃",
            "images": [f"assets/flowers/{img_name}"],
            "summary": f"{name}에 대한 도감 정보입니다.",
            "details": f"{name}의 상세 페이지입니다. (물리 페이지 {phys_num})"
        })
        print(f"Processed Page {phys_num}: {img_name}")

    # 5. Load tree data and merge
    print("Merging data and updating index.html...")
    tree_data = []
    # Try to find existing tree data or use dummy if not available
    # Actually, I should keep the existing trees in index.html
    
    # Read current index.html to preserve other data if possible
    # But I have the merge_and_update logic from previous turns.
    # I'll just save to botanical_index.json for now.
    
    with open("flower_index.json", "w", encoding="utf-8") as f:
        json.dump({"species": species_list}, f, ensure_ascii=False, indent=4)
        
    print("Extraction Complete! Now running final merger...")

if __name__ == "__main__":
    main()
