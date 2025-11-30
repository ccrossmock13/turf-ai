from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("REMOVING TXT FILE LINKS\n")
print("Keeping only real PDFs...\n")

results = index.query(
    vector=[0.0] * 1536,
    top_k=10000,
    include_metadata=True
)

removed = 0

for match in results['matches']:
    metadata = match['metadata']
    pdf_path = metadata.get('pdf_path', '')
    
    # Remove if it points to a .txt file
    if pdf_path and pdf_path.endswith('.txt'):
        try:
            fetch_result = index.fetch(ids=[match['id']])
            if match['id'] not in fetch_result['vectors']:
                continue
            
            vector_data = fetch_result['vectors'][match['id']]
            updated_metadata = vector_data['metadata']
            
            # Remove txt path
            del updated_metadata['pdf_path']
            
            # Re-upsert
            index.upsert(vectors=[{
                'id': match['id'],
                'values': vector_data['values'],
                'metadata': updated_metadata
            }])
            
            removed += 1
            
            if removed % 50 == 0:
                print(f"  Removed {removed} txt links...")
                
        except Exception as e:
            print(f"  Error: {e}")

print(f"\n{'='*70}")
print(f"✅ COMPLETE!")
print(f"{'='*70}")
print(f"Removed {removed} txt file links")
print(f"\nLibrary now only shows products with real PDFs")