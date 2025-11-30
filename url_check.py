from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

# Check a product label
results = index.query(
    vector=[0.0] * 1536,
    top_k=1,
    filter={"source": {"$eq": "Heritage Label"}},
    include_metadata=True
)

if results['matches']:
    meta = results['matches'][0]['metadata']
    print(f"Source: {meta.get('source')}")
    print(f"pdf_path: {meta.get('pdf_path')}")
    print(f"label_url: {meta.get('label_url')}")
    print(f"url: {meta.get('url')}")