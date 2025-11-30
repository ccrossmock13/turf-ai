import PyPDF2
import openai
from pinecone import Pinecone
import os
from dotenv import load_dotenv
import glob
import time

load_dotenv()

# Initialize
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

# Find all PDFs
pdf_files = glob.glob("*.pdf")
print(f"\n{'='*60}")
print(f"TURF AI - BATCH UPLOAD")
print(f"{'='*60}")
print(f"Found {len(pdf_files)} PDF files\n")

# Stats
total_papers = len(pdf_files)
total_chunks_uploaded = 0
failed_papers = []
chunks_per_paper = 30

start_time = time.time()

for idx, pdf_file in enumerate(pdf_files, 1):
    print(f"\n[{idx}/{total_papers}] Processing: {pdf_file}")
    print("-" * 60)
    
    try:
        # Extract text
        pdf = open(pdf_file, 'rb')
        pdf_reader = PyPDF2.PdfReader(pdf)
        
        full_text = ""
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                full_text += text
        
        pdf.close()
        
        if len(full_text) < 500:
            print(f"⚠ Skipped - insufficient text ({len(full_text)} chars)")
            continue
        
        print(f"✓ Extracted {len(full_text):,} characters from {len(pdf_reader.pages)} pages")
        
        # Split into chunks
        chunk_size = 1000
        chunks = []
        for i in range(0, len(full_text), chunk_size):
            chunk = full_text[i:i+chunk_size]
            if len(chunk) > 200:  # Skip tiny chunks
                chunks.append(chunk)
        
        print(f"✓ Created {len(chunks)} chunks (uploading first {chunks_per_paper})")
        
        # Embed and upload
        uploaded = 0
        for i, chunk in enumerate(chunks[:chunks_per_paper]):
            try:
                response = openai_client.embeddings.create(
                    input=chunk,
                    model="text-embedding-3-small"
                )
                embedding = response.data[0].embedding
                
                # Upload to Pinecone
                index.upsert(vectors=[{
                    "id": f"{pdf_file.replace('.pdf', '')}-chunk-{i}",
                    "values": embedding,
                    "metadata": {
                        "text": chunk,
                        "source": pdf_file,
                        "chunk_id": i,
                        "total_chunks": len(chunks)
                    }
                }])
                
                uploaded += 1
                
                if (i+1) % 10 == 0:
                    print(f"  → Uploaded {i+1}/{min(chunks_per_paper, len(chunks))} chunks")
                
            except Exception as e:
                print(f"  ✗ Error on chunk {i}: {e}")
        
        total_chunks_uploaded += uploaded
        print(f"✓ Successfully uploaded {uploaded} chunks from {pdf_file}")
        
    except Exception as e:
        print(f"✗ FAILED: {pdf_file} - {e}")
        failed_papers.append(pdf_file)

# Final stats
elapsed = time.time() - start_time
minutes = int(elapsed // 60)
seconds = int(elapsed % 60)

print(f"\n{'='*60}")
print(f"UPLOAD COMPLETE")
print(f"{'='*60}")
print(f"Papers processed: {total_papers - len(failed_papers)}/{total_papers}")
print(f"Total chunks uploaded: {total_chunks_uploaded}")
print(f"Time elapsed: {minutes}m {seconds}s")
print(f"Chunks per paper: {chunks_per_paper}")

if failed_papers:
    print(f"\n⚠ Failed papers ({len(failed_papers)}):")
    for paper in failed_papers:
        print(f"  - {paper}")

print(f"\n🌱 Your Turf AI database now contains {total_chunks_uploaded} searchable chunks!")
print(f"{'='*60}\n")
