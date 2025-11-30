from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("RENAMING: Econ Survey Exec Summary → Bauer Research Paper\n")

results = index.query(
    vector=[0.0] * 1536,
    top_k=10000,
    include_metadata=True
)

found = []
for match in results['matches']:
    metadata = match['metadata']
    
    for field in ['product_name', 'document_name', 'source']:
        name = metadata.get(field, '')
        if 'econ' in name.lower() and 'exec' in name.lower():
            found.append(match['id'])
            print(f"Found: {name}")
            break

print(f"\n{len(found)} vectors found")
confirm = input("Rename to 'Bauer Research Paper' and change to university_extension? (yes/no): ").strip().lower()

if confirm == 'yes':
    updated = 0
    for vector_id in found:
        try:
            fetch_result = index.fetch(ids=[vector_id])
            if vector_id not in fetch_result['vectors']:
                continue
            
            vector_data = fetch_result['vectors'][vector_id]
            updated_metadata = vector_data['metadata']
            
            # Update all name fields
            updated_metadata['document_name'] = 'Bauer Research Paper'
            updated_metadata['source'] = 'Bauer Research Paper'
            if 'product_name' in updated_metadata:
                updated_metadata['product_name'] = 'Bauer Research Paper'
            updated_metadata['type'] = 'university_extension'
            updated_metadata['brand'] = 'Research'
            
            # Link to the Bauer PDF if it exists
            if os.path.exists('static/pdfs/Bauer_Samuel_May2011.pdf'):
                updated_metadata['pdf_path'] = '/static/pdfs/Bauer_Samuel_May2011.pdf'
            
            index.upsert(vectors=[{
                'id': vector_id,
                'values': vector_data['values'],
                'metadata': updated_metadata
            }])
            
            updated += 1
            if updated % 5 == 0:
                print(f"Updated {updated}...")
        
        except Exception as e:
            print(f"Error: {e}")
    
    print(f"\n✅ Renamed {updated} vectors")