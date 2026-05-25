from pinecone import Pinecone, ServerlessSpec
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

# Create index
index_name = "turf-research"

# Check if index already exists
existing_indexes = [index.name for index in pc.list_indexes()]

if index_name not in existing_indexes:
    print(f"Creating index '{index_name}'...")
    pc.create_index(
        name=index_name,
        dimension=1536,  # OpenAI embedding size
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )
    print("Index created!")
else:
    print(f"Index '{index_name}' already exists!")

print("\nYour Pinecone setup is ready!")
