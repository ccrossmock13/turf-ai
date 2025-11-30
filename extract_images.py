from pdf2image import convert_from_path
import os
from PIL import Image
import glob

# Create images folder
if not os.path.exists('static'):
    os.makedirs('static')
if not os.path.exists('static/images'):
    os.makedirs('static/images')

# Find all equipment manuals
pdf_files = glob.glob("equipment_manuals/*.pdf")

print(f"\n{'='*60}")
print(f"EXTRACTING IMAGES FROM EQUIPMENT MANUALS")
print(f"{'='*60}")
print(f"Found {len(pdf_files)} PDF files\n")

total_images = 0

for idx, pdf_file in enumerate(pdf_files, 1):
    filename = os.path.basename(pdf_file).replace('.pdf', '')
    print(f"[{idx}/{len(pdf_files)}] Processing: {filename}")
    
    try:
        # Convert PDF pages to images
        pages = convert_from_path(pdf_file, dpi=150)
        
        print(f"  Found {len(pages)} pages")
        
        # Save each page as an image
        for page_num, page in enumerate(pages, 1):
            # Save as JPEG
            output_path = f"static/images/{filename}_page_{page_num}.jpg"
            page.save(output_path, 'JPEG', quality=85)
            total_images += 1
        
        print(f"  ✓ Saved {len(pages)} page images")
        
    except Exception as e:
        print(f"  ✗ Error: {e}")

print(f"\n{'='*60}")
print(f"EXTRACTION COMPLETE")
print(f"{'='*60}")
print(f"Total images extracted: {total_images}")
print(f"Saved to: static/images/")
print(f"{'='*60}\n")
