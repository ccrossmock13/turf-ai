from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("\n" + "="*70)
print("DATABASE LABEL AUDIT")
print("="*70 + "\n")

# Get index stats
stats = index.describe_index_stats()
total_vectors = stats['total_vector_count']
print(f"Total vectors in database: {total_vectors}\n")

# Query all vectors by brand
brands = ['Syngenta', 'Envu', 'Floratine', 'Plant Food Company']

for brand in brands:
    print(f"\n{'='*70}")
    print(f"{brand.upper()} PRODUCTS")
    print(f"{'='*70}\n")
    
    # Fetch sample of products from this brand
    # We'll do a dummy query to get matches
    results = index.query(
        vector=[0.0] * 1536,  # Dummy vector
        top_k=10000,
        include_metadata=True,
        filter={"brand": {"$eq": brand}}
    )
    
    products_with_labels = []
    products_without_labels = []
    
    for match in results['matches']:
        metadata = match['metadata']
        product_name = metadata.get('product_name', 'Unknown')
        text = metadata.get('text', '')
        label_url = metadata.get('label_url', '')
        
        has_label = 'label information:' in text.lower() or len(text) > 2000
        
        if has_label or label_url:
            products_with_labels.append({
                'name': product_name,
                'id': match['id'],
                'label_url': label_url,
                'text_length': len(text)
            })
        else:
            products_without_labels.append({
                'name': product_name,
                'id': match['id'],
                'text_length': len(text)
            })
    
    print(f"✅ Products WITH labels: {len(products_with_labels)}")
    if products_with_labels:
        for p in sorted(set([x['name'] for x in products_with_labels])):
            print(f"   • {p}")
    
    print(f"\n❌ Products WITHOUT labels: {len(products_without_labels)}")
    if products_without_labels:
        for p in sorted(set([x['name'] for x in products_without_labels])):
            print(f"   • {p}")
    
    print(f"\n📊 Label Coverage: {len(products_with_labels)}/{len(products_with_labels) + len(products_without_labels)} ({100*len(products_with_labels)/(len(products_with_labels) + len(products_without_labels)) if (len(products_with_labels) + len(products_without_labels)) > 0 else 0:.1f}%)")

print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}\n")
print("Run your scrapers again for products missing labels.")
print("Check that PDF links are being found correctly.")