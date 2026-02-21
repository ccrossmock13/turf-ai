from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

results = index.query(
    vector=[0.0] * 1536,
    top_k=50,
    include_metadata=True
)

print("FIRST 50 PRODUCTS IN PINECONE:\n")
for i, match in enumerate(results['matches'][:50], 1):
    metadata = match['metadata']
    name = metadata.get('product_name') or metadata.get('document_name') or metadata.get('source', 'NO NAME')
    ptype = metadata.get('type', 'unknown')
    brand = metadata.get('brand', 'unknown')
    
    print(f"{i}. {name} | Type: {ptype} | Brand: {brand}")