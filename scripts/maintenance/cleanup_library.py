from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("LIBRARY CLEANUP TOOL\n")
print("Options:")
print("1. Show all unique products in library")
print("2. Delete vectors with wrong EPA links")
print("3. Remove duplicate products (keep best one)")
print("4. Show products with EPA links\n")

choice = input("Enter choice (1-4): ").strip()

if choice == "1":
    # Show all unique products
    results = index.query(
        vector=[0.0] * 1536,
        top_k=10000,
        filter={"type": {"$in": ["pesticide_label", "pesticide_product", "ntep_trial"]}},
        include_metadata=True
    )
    
    seen = {}
    for match in results['matches']:
        metadata = match['metadata']
        name = metadata.get('product_name') or metadata.get('document_name') or metadata.get('source', '')
        ptype = metadata.get('type', '')
        brand = metadata.get('brand', '')
        
        key = f"{brand}_{name}_{ptype}"
        if key not in seen:
            seen[key] = 0
        seen[key] += 1
    
    print(f"\nFound {len(seen)} unique products:\n")
    for key, count in sorted(seen.items()):
        brand, name, ptype = key.split('_', 2)
        print(f"{name} ({brand}) - {count} chunks")

elif choice == "2":
    # Find and delete vectors with wrong EPA links
    product_name = input("\nEnter product name to fix: ").strip()
    
    results = index.query(
        vector=[0.0] * 1536,
        top_k=100,
        filter={"type": {"$in": ["pesticide_label", "pesticide_product"]}},
        include_metadata=True
    )
    
    to_delete = []
    for match in results['matches']:
        metadata = match['metadata']
        name = (metadata.get('product_name') or metadata.get('document_name') or metadata.get('source', '')).lower()
        
        if product_name.lower() in name:
            print(f"\nFound: {metadata.get('product_name')}")
            print(f"  ID: {match['id']}")
            print(f"  EPA Link: {metadata.get('label_url', 'None')}")
            delete = input("  Delete this vector? (y/n): ").strip().lower()
            if delete == 'y':
                to_delete.append(match['id'])
    
    if to_delete:
        confirm = input(f"\nDelete {len(to_delete)} vectors? (yes/no): ").strip().lower()
        if confirm == 'yes':
            index.delete(ids=to_delete)
            print(f"✅ Deleted {len(to_delete)} vectors")

elif choice == "3":
    # Remove duplicates - keep one with best metadata
    results = index.query(
        vector=[0.0] * 1536,
        top_k=10000,
        filter={"type": {"$in": ["pesticide_label", "pesticide_product", "ntep_trial"]}},
        include_metadata=True
    )
    
    # Group by product name
    products = {}
    for match in results['matches']:
        metadata = match['metadata']
        name = metadata.get('product_name') or metadata.get('document_name') or metadata.get('source', '')
        brand = metadata.get('brand', 'Unknown')
        
        key = f"{brand}_{name}"
        if key not in products:
            products[key] = []
        products[key].append(match['id'])
    
    # Find duplicates (products with multiple chunks is normal, but same exact name from same brand multiple times is duplicate)
    duplicates = {k: v for k, v in products.items() if len(v) > 50}  # More than 50 chunks is suspicious
    
    print(f"\nFound {len(duplicates)} potential duplicate products:\n")
    for key, ids in sorted(duplicates.items())[:20]:
        print(f"{key}: {len(ids)} chunks")
    
    print("\nNote: Some products legitimately have many chunks (long labels)")
    print("Manual review recommended before deletion")

elif choice == "4":
    # Show products with EPA links
    results = index.query(
        vector=[0.0] * 1536,
        top_k=10000,
        filter={"label_url": {"$exists": True}},
        include_metadata=True
    )
    
    seen = set()
    print(f"\nProducts with EPA links:\n")
    for match in results['matches']:
        metadata = match['metadata']
        name = metadata.get('product_name') or metadata.get('document_name') or metadata.get('source', '')
        url = metadata.get('label_url', '')
        
        if name not in seen:
            seen.add(name)
            print(f"{name}")
            print(f"  {url}\n")

print("\n✅ Done")