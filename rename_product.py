from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("RENAMING: Bmps Irrigating Golf Course Turf Rutgers Univ → Toro Irrigation Catalog\n")

results = index.query(
    vector=[0.0] * 1536,
    top_k=10000,
    include_metadata=True
)

found = []
for match in results['matches']:
    metadata = match['metadata']
    
    # Check all possible name fields
    for field in ['product_name', 'document_name', 'source']:
        name = metadata.get(field, '')
        if 'bmps irrigating' in name.lower():
            found.append(match['id'])
            print(f"Found: {name}")
            break

if not found:
    print(f"Not found. Searching for ANY 'irrigating' reference...")
    for match in results['matches']:
        metadata = match['metadata']
        for field in ['product_name', 'document_name', 'source']:
            name = metadata.get(field, '')
            if 'irrigating' in name.lower():
                print(f"  Found: {name}")
                break
    exit()

print(f"\n{len(found)} vectors found")
confirm = input("Rename to 'Toro Irrigation Catalog'? (yes/no): ").strip().lower()

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
            updated_metadata['document_name'] = 'Toro Irrigation Catalog'
            updated_metadata['source'] = 'Toro Irrigation Catalog'
            if 'product_name' in updated_metadata:
                updated_metadata['product_name'] = 'Toro Irrigation Catalog'
            updated_metadata['type'] = 'equipment_catalog'
            updated_metadata['brand'] = 'Toro'
            
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