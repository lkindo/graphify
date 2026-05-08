import fitz
import re
import json

def extract_column_text():
    doc = fitz.open("pdf/index.pdf")
    all_pairs = []
    
    for page in doc:
        width = page.rect.width
        # Divide into 3 columns
        col_width = width / 3
        for i in range(3):
            rect = fitz.Rect(i * col_width, 0, (i + 1) * col_width, page.rect.height)
            text = page.get_text("text", clip=rect)
            
            # Now parse this column's text
            lines = text.split('\n')
            current_name = None
            for line in lines:
                line = line.strip()
                if not line: continue
                
                # If it's a number, it belongs to the current_name
                if re.fullmatch(r'\d+', line):
                    if current_name:
                        all_pairs.append({"name": current_name, "page": int(line)})
                        current_name = None
                else:
                    # It's a name
                    current_name = line
                    
    return all_pairs

def main():
    pairs = extract_column_text()
    # Clean names
    for p in pairs:
        p["name"] = "".join(re.findall(r'[가-힣]+', p["name"]))
    
    # Filter valid ones
    pairs = [p for p in pairs if p["name"] and 10 <= p["page"] <= 304]
    
    # Sort by page
    pairs.sort(key=lambda x: x["page"])
    
    with open("cleaned_index.json", "w", encoding="utf-8") as f:
        json.dump(pairs, f, ensure_ascii=False, indent=4)
        
    print(f"Extracted {len(pairs)} cleaned pairs.")

if __name__ == "__main__":
    main()
