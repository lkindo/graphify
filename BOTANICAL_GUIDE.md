# Botanical Data Extraction Guidelines

This document defines the page ranges and extraction rules for the Korean Tree Encyclopedia (Volumes 1-4).

## Page Range Definitions (User-provided Page Numbers)
*Note: Physical PDF Page = User Page + 1*

### Volume 1 (koreantree1.pdf)
- **Table of Contents (TOC)**: 16 ~ 19
- **Plant Images/Content**: 20 ~ 409

### Volume 2 (koreantree2.pdf)
- **Table of Contents (TOC)**: 8 ~ 11
- **Plant Images/Content**: 12 ~ 439

### Volume 3 (koreantree3.pdf)
- **Table of Contents (TOC)**: 8 ~ 11
- **Plant Images/Content**: 12 ~ 411

### Volume 4 (koreantree4.pdf)
- **Table of Contents (TOC)**: 8 ~ 11
- **Plant Images/Content**: 12 ~ 387

## Extraction Rules
1. **Name Extraction**: Parse the TOC within the specified range. For each entry, look at the corresponding content page (User Page + 1) to find the exact plant name, avoiding family names (ending in '과').
2. **Image Extraction**: Collect up to 2 high-quality images (>= 10KB) per species within the assigned page range.
3. **Offset**: Use a consistent offset of **+1** to map printed page numbers to PDF physical pages.
