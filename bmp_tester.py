from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

# Find first 5 state BMPs to see naming
results = index.query(
    vector=[0.0] * 1536,
    top_k=10000,
    include_metadata=True
)

bmp_sources = []
for match in results['matches']:
    source = match['metadata'].get('source', '')
    if 'bmp' in source.lower() and any(state in source.lower() for state in ['texas', 'alabama', 'georgia', 'massachusetts']):
        bmp_sources.append(source)
        if len(bmp_sources) <= 10:
            print(f"Source: '{source}'")

print(f"\nTotal state BMP sources found: {len(bmp_sources)}")