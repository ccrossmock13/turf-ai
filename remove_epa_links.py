from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("CLEANING UP BAD EPA LINKS\n")

# Query all vectors with label_url
results = index.query(
    vector=[0.0] * 1536,
    top_k=10000,
    include_metadata=True
)

removed_epa = 0
kept_greencast = 0

for match in results['matches']:
    metadata = match['metadata']
    
    if not metadata.get('label_url') and not metadata.get('pdf_path'):
        continue
    
    label_url = metadata.get('label_url', '')
    pdf_path = metadata.get('pdf_path', '')
    
    # Keep Greencast links (these are good direct links from Syngenta)
    if 'greencastonline.com' in label_url or 'basf.ca' in label_url:
        kept_greencast += 1
        continue
    
    # Remove EPA links (these are wrong)
    if 'epa.gov' in label_url or 'epa.gov' in pdf_path:
        try:
            # Fetch vector
            fetch_result = index.fetch(ids=[match['id']])
            if match['id'] not in fetch_result['vectors']:
                continue
            
            vector_data = fetch_result['vectors'][match['id']]
            updated_metadata = vector_data['metadata']
            
            # Remove bad URLs
            if 'label_url' in updated_metadata:
                del updated_metadata['label_url']
            if 'pdf_path' in updated_metadata and 'epa.gov' in updated_metadata['pdf_path']:
                del updated_metadata['pdf_path']
            
            # Re-upsert
            index.upsert(vectors=[{
                'id': match['id'],
                'values': vector_data['values'],
                'metadata': updated_metadata
            }])
            
            removed_epa += 1
            
            if removed_epa % 100 == 0:
                print(f"  Cleaned {removed_epa} vectors...")
                
        except Exception as e:
            print(f"  Error: {e}")

print(f"\n{'='*70}")
print(f"✅ CLEANUP COMPLETE!")
print(f"{'='*70}")
print(f"Removed bad EPA links: {removed_epa}")
print(f"Kept good Greencast links: {kept_greencast}")
print(f"\nLibrary now only shows products with real PDF links")