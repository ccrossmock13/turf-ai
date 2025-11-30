from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

# Get stats
stats = index.describe_index_stats()
print(f"Total vectors: {stats['total_vector_count']}\n")

# Try to fetch by type instead
results = index.query(
    vector=[0.0] * 1536,
    top_k=100,  # Get more results
    filter={"type": "reference_document"},  # Filter for those garbage ones
    include_metadata=True
)

print(f"Found {len(results['matches'])} reference_document vectors\n")

if results['matches']:
    match = results['matches'][0]
    metadata = match['metadata']
    
    print(f"Vector ID: {match['id']}\n")
    print("ALL METADATA:")
    for key, value in metadata.items():
        if key != 'text':
            print(f"  {key}: {value}")
    print(f"\nFirst 500 chars of text:")
    print(metadata.get('text', '')[:500])