from pinecone import Pinecone
import os
from dotenv import load_dotenv
import re

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("GCM MAGAZINE RENAMER\n")
print("="*80)

# Query all vectors
results = index.query(
    vector=[0.0] * 1536,
    top_k=10000,
    include_metadata=True
)

# Find GCM magazines by filename pattern
gcm_vectors = []
month_names = {
    'jan': 'January', 'feb': 'February', 'mar': 'March',
    'apr': 'April', 'may': 'May', 'jun': 'June',
    'jul': 'July', 'aug': 'August', 'sep': 'September',
    'oct': 'October', 'nov': 'November', 'dec': 'December'
}

for match in results['matches']:
    metadata = match['metadata']
    
    # Check document_name, source, or original_filename
    for field in ['document_name', 'source', 'original_filename']:
        name = metadata.get(field, '').lower()
        
        # Match pattern like 2024jan, 2019feb, etc.
        gcm_match = re.match(r'^(\d{4})(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', name)
        
        if gcm_match:
            year = gcm_match.group(1)
            month_abbr = gcm_match.group(2)
            new_name = f"GCM Magazine {month_names[month_abbr]} {year}"
            
            gcm_vectors.append({
                'id': match['id'],
                'old_name': metadata.get('document_name') or metadata.get('source'),
                'new_name': new_name,
                'metadata': metadata
            })
            break

# Show unique GCM magazines found
unique_gcm = {}
for vec in gcm_vectors:
    if vec['new_name'] not in unique_gcm:
        unique_gcm[vec['new_name']] = 0
    unique_gcm[vec['new_name']] += 1

print(f"Found {len(unique_gcm)} GCM magazines:\n")
for name, count in sorted(unique_gcm.items()):
    print(f"  {name} ({count} chunks)")

print(f"\nTotal vectors to rename: {len(gcm_vectors)}")

if not gcm_vectors:
    print("No GCM magazines found")
    exit()

confirm = input("\nRename all GCM magazines? (yes/no): ").strip().lower()

if confirm == 'yes':
    updated = 0
    
    for vec in gcm_vectors:
        try:
            # Fetch vector
            fetch_result = index.fetch(ids=[vec['id']])
            if vec['id'] not in fetch_result['vectors']:
                continue
            
            vector_data = fetch_result['vectors'][vec['id']]
            updated_metadata = vector_data['metadata']
            
            # Update all name fields
            updated_metadata['document_name'] = vec['new_name']
            updated_metadata['source'] = vec['new_name']
            if 'product_name' in updated_metadata:
                updated_metadata['product_name'] = vec['new_name']
            
            # Set type and brand
            updated_metadata['type'] = 'university_extension'
            updated_metadata['brand'] = 'GCM Magazine'
            
            # Re-upsert
            index.upsert(vectors=[{
                'id': vec['id'],
                'values': vector_data['values'],
                'metadata': updated_metadata
            }])
            
            updated += 1
            
            if updated % 20 == 0:
                print(f"  Updated {updated}/{len(gcm_vectors)}...")
        
        except Exception as e:
            print(f"  Error: {e}")
    
    print(f"\n{'='*80}")
    print(f"✅ COMPLETE!")
    print(f"{'='*80}")
    print(f"Renamed {updated} vectors")
    print(f"GCM magazines now show as 'GCM Magazine January 2024' etc.")

else:
    print("Cancelled")