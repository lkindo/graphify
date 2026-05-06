import pypdf
import re

reader = pypdf.PdfReader('pdf/tree.pdf')
for i in range(290, 310):
    text = reader.pages[i].extract_text()
    if '296' in text:
        print(f"PDF Page {i+1} contains '296'")
    if '300' in text:
        print(f"PDF Page {i+1} contains '300'")
    if '산딸나무' in text:
        print(f"PDF Page {i+1} contains '산딸나무'")
    if '층층나무' in text:
        print(f"PDF Page {i+1} contains '층층나무'")
