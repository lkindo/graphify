import fitz

def debug_page_1():
    doc = fitz.open("pdf/flower.pdf")
    page = doc[0]
    blocks = page.get_text("blocks")
    for i, b in enumerate(blocks):
        # b = (x0, y0, x1, y1, "text", block_no, block_type)
        print(f"Block {i}: {b[:4]} -> {repr(b[4])}")

if __name__ == "__main__":
    debug_page_1()
