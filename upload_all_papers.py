import PyPDF2
import openai
from pinecone import Pinecone
import os
from dotenv import load_dotenv
import glob

load_dotenv()

# Initialize
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

# Find all PDFs in folder
pdf_files = glob.glob("*.pdf")
print(f"Found {len(pdf_files)} PDF files")

total_chunks = 0

for pdf_file in pdf_files:
    print(f"\n{'='*50}")
    print(f"Processing: {pdf_file}")
    print(f"{'='*50}")
    
    try:
        # Extract text
        pdf = open(pdf_file, 'rb')
        pdf_reader = PyPDF2.PdfReader(pdf)
        
        full_text = ""
        for page in pdf_reader.pages:
            full_text += page.extract_text()
        
        pdf.close()
        
        print(f"Extracted {len(full_text)} characters")
        
        # Split into chunks
        chunk_size = 1000
        chunks = []
        for i in range(0, len(full_text), chunk_size):
            chunk = full_text[i:i+chunk_size]
            if len(chunk) > 100:  # Skip tiny chunks
                chunks.append(chunk)
        
        print(f"Created {len(chunks)} chunks")
        
        # Embed and upload (first 20 chunks per paper to save API costs)
        for i, chunk in enumerate(chunks[:20]):
            response = openai_client.embeddings.create(
                input=chunk,
                model="text-embedding-3-small"
            )
            embedding = response.data[0].embedding
            
            # Upload to Pinecone
            index.upsert(vectors=[{
                "id": f"{pdf_file}-chunk-{i}",
                "values": embedding,
                "metadata": {
                    "text": chunk,
                    "source": pdf_file,
                    "chunk_id": i
                }
            }])
            
            if (i+1) % 5 == 0:
                print(f"  Uploaded {i+1}/{min(20, len(chunks))} chunks")
        
        total_chunks += min(20, len(chunks))
        print(f"✓ Done with {pdf_file}")
        
    except Exception as e:
        print(f"✗ Error processing {pdf_file}: {e}")

print(f"\n{'='*50}")
print(f"COMPLETE!")
print(f"Total chunks uploaded: {total_chunks}")
print(f"Your Turf AI now has {len(pdf_files)} papers!")
print(f"{'='*50}")
