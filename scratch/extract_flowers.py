import fitz
import re
import os
import json

def clean_name(text):
    if not text: return ""
    # Extract only Korean characters
    name = "".join(re.findall(r'[가-힣]+', text))
    return name

def extract_flowers():
    doc = fitz.open("pdf/flower.pdf")
    output_dir = "assets/flowers"
    os.makedirs(output_dir, exist_ok=True)
    
    species_list = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Get detailed text dict
        data = page.get_text("dict")
        
        # Find the largest font size span in the top area (y < 150)
        max_size = 0
        name = ""
        
        for block in data["blocks"]:
            if block["type"] == 0: # Text block
                for line in block["lines"]:
                    for span in line["spans"]:
                        # Look at spans in the top part of the page
                        if span["bbox"][1] < 150:
                            cleaned = clean_name(span["text"])
                            if cleaned and len(cleaned) <= 15:
                                if span["size"] > max_size:
                                    max_size = span["size"]
                                    name = cleaned
        
        if not name:
            name = f"page_{page_num + 1}"
        
        # If name already exists, append page number
        final_name = name
        counter = 1
        while os.path.exists(os.path.join(output_dir, f"{final_name}.png")):
            final_name = f"{name}_{counter}"
            counter += 1
            
        print(f"Page {page_num + 1}: Name -> {final_name}")
        
        # Render page
        # Use higher zoom for better quality
        zoom = 2
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        fname = f"{final_name}.png"
        pix.save(os.path.join(output_dir, fname))
        
        species_list.append({
            "name": final_name,
            "category": "나무에 피는 꽃",
            "images": [f"assets/flowers/{fname}"],
            "summary": f"{final_name}에 대한 정보입니다.",
            "details": f"{final_name}의 도감 페이지입니다."
        })

    with open("flower_index.json", "w", encoding="utf-8") as f:
        json.dump({"species": species_list}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    extract_flowers()
