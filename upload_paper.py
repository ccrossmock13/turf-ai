import PyPDF2
import openai
from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("Extracting text from PDF...")

# Extract all text from PDF
pdf_file = open('paper.pdf', 'rb')
pdf_reader = PyPDF2.PdfReader(pdf_file)

full_text = ""
for page in pdf_reader.pages:
    full_text += page.extract_text()

pdf_file.close()

print(f"Extracted {len(full_text)} characters")

# Split into chunks (simple version - every 1000 characters)
chunk_size = 1000
chunks = []
for i in range(0, len(full_text), chunk_size):
    chunk = full_text[i:i+chunk_size]
    chunks.append(chunk)

print(f"Created {len(chunks)} chunks")

# Embed and upload each chunk
print("Embedding and uploading to Pinecone...")

for i, chunk in enumerate(chunks[:10]):  # Just first 10 chunks to test
    # Create embedding
    response = openai_client.embeddings.create(
        input=chunk,
        model="text-embedding-3-small"
    )
    embedding = response.data[0].embedding
    
    # Upload to Pinecone
    index.upsert(vectors=[{
        "id": f"paper-chunk-{i}",
        "values": embedding,
        "metadata": {"text": chunk, "source": "Fleetwood Dissertation"}
    }])
    
    print(f"Uploaded chunk {i+1}/10")

print("\nDone! Your paper is now searchable in Pinecone!")