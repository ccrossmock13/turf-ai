from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("DELETING SPECIFIC PRODUCTS\n")

# Products to delete
delete_keywords = [
    'bmp anthracnose',
    'bmp nutrient management',
    'bmp rutgers university',
    'disease calendar'
]

results = index.query(
    vector=[0.0] * 1536,
    top_k=10000,
    include_metadata=True
)

to_delete = []

for match in results['matches']:
    metadata = match['metadata']
    name = (metadata.get('product_name') or metadata.get('document_name') or metadata.get('source', '')).lower()
    
    # Check if this product should be deleted
    for keyword in delete_keywords:
        if keyword in name:
            to_delete.append(match['id'])
            print(f"Marked for deletion: {metadata.get('document_name') or metadata.get('product_name')}")
            break

print(f"\nFound {len(to_delete)} vectors to delete")
confirm = input(f"Delete these {len(to_delete)} vectors? (yes/no): ").strip().lower()

if confirm == 'yes':
    # Delete in batches of 100
    for i in range(0, len(to_delete), 100):
        batch = to_delete[i:i+100]
        index.delete(ids=batch)
        print(f"Deleted {min(i+100, len(to_delete))}/{len(to_delete)}...")
    
    print(f"\n✅ Deleted {len(to_delete)} vectors")
else:
    print("Cancelled")