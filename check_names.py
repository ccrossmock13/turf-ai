from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

results = index.query(
    vector=[0.0] * 1536,
    top_k=100,
    filter={"type": "university_extension"},
    include_metadata=True
)

seen = set()
print("University Extension products:\n")
for match in results['matches']:
    metadata = match['metadata']
    name = metadata.get('product_name') or metadata.get('document_name') or metadata.get('source', '')
    
    if name not in seen:
        seen.add(name)
        print(f"'{name}'")