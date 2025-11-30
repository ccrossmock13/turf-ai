import os
from pinecone import Pinecone
from dotenv import load_dotenv
from difflib import SequenceMatcher
import re

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("PDF LINKING SCRIPT\n")
print("Scanning static folder for PDFs and linking to Pinecone...\n")

# Scan for all PDFs in static folder
PDF_FOLDERS = [
    'static/epa_labels',
    'static/equipment_manuals',
    'static/floratine_products',
    'static/ntep_pdfs',
    'static/pdfs',
    'static/pesticide_pdfs'
]

def normalize_name(name):
    """Normalize product/file name for matching"""
    # Remove extension, convert to lowercase
    name = name.lower()
    name = re.sub(r'\.(pdf|txt)$', '', name)
    
    # Remove EPA registration numbers (e.g., 100-1326, 101563-21)
    name = re.sub(r'_?\d{2,6}-\d{1,4}', '', name)
    
    # Remove standalone dashes and numbers at end
    name = re.sub(r'_-$', '', name)
    name = re.sub(r'-$', '', name)
    
    # Replace underscores with spaces
    name = name.replace('_', ' ')
    
    # Remove special chars except spaces
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name

def similarity(a, b):
    """Calculate similarity between two strings"""
    return SequenceMatcher(None, a, b).ratio()

# Step 1: Find all PDFs
print("="*70)
print("STEP 1: SCANNING FOR PDFs AND TXT FILES")
print("="*70 + "\n")

all_pdfs = []
for folder in PDF_FOLDERS:
    if not os.path.exists(folder):
        print(f"⚠️  Folder not found: {folder}")
        continue
    
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith('.pdf') or file.endswith('.txt'):
                full_path = os.path.join(root, file)
                # Convert to web path
                web_path = '/' + full_path.replace('\\', '/')
                all_pdfs.append({
                    'filename': file,
                    'normalized': normalize_name(file),
                    'path': web_path
                })

print(f"Found {len(all_pdfs)} PDFs total\n")

# Step 2: Get all products from Pinecone
print("="*70)
print("STEP 2: QUERYING PINECONE FOR ALL PRODUCTS")
print("="*70 + "\n")

results = index.query(
    vector=[0.0] * 1536,
    top_k=10000,
    include_metadata=True
)

print(f"Found {len(results['matches'])} vectors in Pinecone\n")

# Step 3: Match PDFs to products
print("="*70)
print("STEP 3: MATCHING PDFs TO PRODUCTS")
print("="*70 + "\n")

updated = 0
skipped = 0

for match in results['matches']:
    metadata = match['metadata']
    vector_id = match['id']
    
    # Get product name
    product_name = (
        metadata.get('product_name') or 
        metadata.get('document_name') or 
        metadata.get('source', '')
    )
    
    if not product_name:
        continue
    
    # Skip garbage codes (codes like cs15l_21-13f, ff20_25-7)
    # These are research paper codes with no real filenames
    if re.match(r'^[a-z]{2}\d{2}[_\-]', product_name.lower()):
        continue
    
    # Skip reference_document type entirely - these are all garbage
    product_type = metadata.get('type', '')
    if product_type == 'reference_document':
        continue
    
    # ONLY process these specific types with real names
    if product_type not in ['pesticide_product', 'pesticide_label', 'ntep_trial']:
        continue
    
    # Skip if already has PDF path
    if metadata.get('pdf_path'):
        skipped += 1
        continue
    
    # Normalize product name
    normalized_product = normalize_name(product_name)
    
    # Find best matching PDF
    best_match = None
    best_score = 0.0
    
    for pdf in all_pdfs:
        score = similarity(normalized_product, pdf['normalized'])
        if score > best_score:
            best_score = score
            best_match = pdf
    
    # If good match (>0.4 similarity), update
    if best_match and best_score > 0.4:
        try:
            # Debug output for first 20 matches
            if updated < 20:
                print(f"  Matching: '{product_name}' → '{best_match['filename']}' (score: {best_score:.2f})")
            
            # Fetch the vector
            fetch_result = index.fetch(ids=[vector_id])
            if vector_id not in fetch_result['vectors']:
                continue
            
            vector_data = fetch_result['vectors'][vector_id]
            
            # Update metadata with PDF path
            updated_metadata = vector_data['metadata']
            updated_metadata['pdf_path'] = best_match['path']
            
            # Re-upsert
            index.upsert(vectors=[{
                'id': vector_id,
                'values': vector_data['values'],
                'metadata': updated_metadata
            }])
            
            updated += 1
            
            if updated % 10 == 0:
                print(f"  Updated {updated} products...")
            
        except Exception as e:
            print(f"  Error updating {vector_id}: {e}")

print(f"\n{'='*70}")
print(f"✅ COMPLETE!")
print(f"{'='*70}")
print(f"Files found (PDFs + TXTs): {len(all_pdfs)}")
print(f"Products updated with file links: {updated}")
print(f"Products skipped (already had file): {skipped}")
print(f"\nYour Resource Library now has clickable file links!")