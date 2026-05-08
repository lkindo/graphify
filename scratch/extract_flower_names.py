import fitz
import re
import json
import os

def clean_name(text):
    if not text: return ""
    # Remove weird characters and whitespace
    text = re.sub(r'[^\w가-힣]', '', text)
    # Remove common stop words or noise
    stop_words = ["꽃말", "낙엽교목", "수고", "분포", "유래", "꽃잎", "수술", "암술", "거꿀달갈형", "타원형", "앙성화", "산방", "취산", "원추", "충매화", "풍매화", "밀원"]
    for sw in stop_words:
        if sw in text: return ""
    # Usually names are 2-6 characters
    if len(text) < 2 or len(text) > 10: return ""
    return text

def extract_species_names():
    doc = fitz.open("pdf/flower.pdf")
    results = []
    
    for i in range(len(doc)):
        page = doc[i]
        blocks = page.get_text("dict")["blocks"]
        
        # Candidate names: large font, top of page
        candidates = []
        for b in blocks:
            if "lines" not in b: continue
            for l in b["lines"]:
                for s in l["spans"]:
                    # Coordinate filter: Top 150 pixels
                    if s["bbox"][1] < 150:
                        name = clean_name(s["text"])
                        if name:
                            candidates.append({
                                "name": name,
                                "size": s["size"],
                                "y": s["bbox"][1]
                            })
        
        # Sort by size (desc) and then y (asc)
        candidates.sort(key=lambda x: (-x["size"], x["y"]))
        
        final_name = f"page_{i+1}"
        if candidates:
            # Pick the largest one
            final_name = candidates[0]["name"]
        
        # Fallback check: if the name is very common or looks wrong, try second candidate
        # But for now, let's just collect them
        results.append({"page": i+1, "name": final_name})
    
    # Save to a report file
    with open("flower_naming_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    print(f"Extracted {len(results)} names. Check flower_naming_report.json")

if __name__ == "__main__":
    extract_species_names()
