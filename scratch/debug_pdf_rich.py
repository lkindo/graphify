import fitz
import json

def debug_page_1_rich():
    doc = fitz.open("pdf/flower.pdf")
    page = doc[0]
    data = page.get_text("dict")
    
    # Remove bytes/images for JSON
    def clean_dict(obj):
        if isinstance(obj, dict):
            return {k: clean_dict(v) for k, v in obj.items() if not isinstance(v, bytes)}
        elif isinstance(obj, list):
            return [clean_dict(v) for v in obj]
        return obj

    with open("pdf_structure.json", "w", encoding="utf-8") as f:
        json.dump(clean_dict(data), f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    debug_page_1_rich()
