from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("ADDING COUNTRY TAGS TO PRODUCTS\n")
print("="*80)

# Products that are Canada-only
canada_only = [
    'dedicate stressgard',
]

# Products available in both USA and Canada
both_countries = [
    'heritage',
    'primo maxx',
    'tenacity',
    'lexicon',
]

# Query all pesticide products
results = index.query(
    vector=[0.0] * 1536,
    top_k=10000,
    filter={"type": {"$in": ["pesticide_product", "pesticide_label"]}},
    include_metadata=True
)

print(f"Found {len(results['matches'])} pesticide vectors\n")

updated_usa = 0
updated_canada = 0
updated_both = 0

for match in results['matches']:
    metadata = match['metadata']
    vector_id = match['id']
    
    product_name = (metadata.get('product_name') or metadata.get('document_name') or metadata.get('source', '')).lower()
    
    # Determine country availability
    country = None
    
    # Check if Canada-only
    if any(can_prod in product_name for can_prod in canada_only):
        country = 'Canada'
        updated_canada += 1
    # Check if both countries
    elif any(both_prod in product_name for both_prod in both_countries):
        country = 'USA,Canada'
        updated_both += 1
    # Default to USA
    else:
        country = 'USA'
        updated_usa += 1
    
    try:
        # Fetch vector
        fetch_result = index.fetch(ids=[vector_id])
        if vector_id not in fetch_result['vectors']:
            continue
        
        vector_data = fetch_result['vectors'][vector_id]
        updated_metadata = vector_data['metadata']
        
        # Add country tag
        updated_metadata['country'] = country
        
        # Re-upsert
        index.upsert(vectors=[{
            'id': vector_id,
            'values': vector_data['values'],
            'metadata': updated_metadata
        }])
        
        if (updated_usa + updated_canada + updated_both) % 50 == 0:
            print(f"  Updated {updated_usa + updated_canada + updated_both} products...")
    
    except Exception as e:
        print(f"  Error: {e}")

print(f"\n{'='*80}")
print(f"✅ COMPLETE!")
print(f"{'='*80}")
print(f"USA only: {updated_usa}")
print(f"Canada only: {updated_canada}")
print(f"Both countries: {updated_both}")
print(f"\nNow update app.py to filter by country='USA'")