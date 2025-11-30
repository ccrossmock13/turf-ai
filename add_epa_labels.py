from pinecone import Pinecone
import os
from dotenv import load_dotenv
import re

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("EPA URL LINKER\n")
print("Reading EPA label txt files and adding URLs to Pinecone...\n")

# Read all txt files in epa_labels folder
epa_folder = "static/epa_labels"
updated = 0

for filename in os.listdir(epa_folder):
    if not filename.endswith('.txt'):
        continue
    
    filepath = os.path.join(epa_folder, filename)
    
    # Read the txt file
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Extract product name and EPA URL
    product_match = re.search(r'PRODUCT:\s*(.+)', content)
    url_match = re.search(r'LABEL LINK:\s*(https://[^\s]+)', content)
    
    if not product_match or not url_match:
        continue
    
    product_name = product_match.group(1).strip()
    epa_url = url_match.group(1).strip()
    
    print(f"Processing: {product_name}")
    print(f"  URL: {epa_url}")
    
    # Search Pinecone for this product
    # Query with product name
    query_response = index.query(
        vector=[0.0] * 1536,
        top_k=100,
        filter={"type": {"$in": ["pesticide_product", "pesticide_label"]}},
        include_metadata=True
    )
    
    # Find matching products
    for match in query_response['matches']:
        metadata = match['metadata']
        vector_name = (
            metadata.get('product_name') or 
            metadata.get('document_name') or 
            metadata.get('source', '')
        ).upper()
        
        # Check if this is the right product
        if product_name.upper() in vector_name or any(word in vector_name for word in product_name.upper().split()[:2]):
            try:
                # Fetch the vector
                fetch_result = index.fetch(ids=[match['id']])
                if match['id'] not in fetch_result['vectors']:
                    continue
                
                vector_data = fetch_result['vectors'][match['id']]
                
                # Update metadata with EPA URL
                updated_metadata = vector_data['metadata']
                updated_metadata['label_url'] = epa_url
                updated_metadata['pdf_path'] = epa_url  # Also set as pdf_path so library shows it
                
                # Re-upsert
                index.upsert(vectors=[{
                    'id': match['id'],
                    'values': vector_data['values'],
                    'metadata': updated_metadata
                }])
                
                updated += 1
                
                if updated % 10 == 0:
                    print(f"  Updated {updated} vectors...")
                
            except Exception as e:
                print(f"  Error: {e}")

print(f"\n{'='*70}")
print(f"✅ COMPLETE!")
print(f"{'='*70}")
print(f"Updated {updated} vectors with EPA URLs")
print(f"\nResource Library now has clickable EPA label links!")