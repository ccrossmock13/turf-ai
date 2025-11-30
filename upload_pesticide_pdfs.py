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

# Find all PDFs in pesticide_pdfs folder
pdf_files = glob.glob("pesticide_pdfs/*.pdf")

print(f"\n{'='*60}")
print(f"UPLOADING PESTICIDE LABEL PDFs")
print(f"{'='*60}")
print(f"Found {len(pdf_files)} PDF files\n")

total_chunks = 0

for idx, pdf_file in enumerate(pdf_files, 1):
    print(f"[{idx}/{len(pdf_files)}] Processing: {os.path.basename(pdf_file)}")
    
    try:
        # Extract text from PDF
        pdf = open(pdf_file, 'rb')
        pdf_reader = PyPDF2.PdfReader(pdf)
        
        full_text = ""
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                full_text += text
        
        pdf.close()
        
        print(f"  Extracted {len(full_text):,} characters from {len(pdf_reader.pages)} pages")
        
        if len(full_text) < 500:
            print(f"  ⚠ Skipped - insufficient text")
            continue
        
        # Split into chunks
        chunk_size = 1000
        chunks = []
        for i in range(0, len(full_text), chunk_size):
            chunk = full_text[i:i+chunk_size]
            if len(chunk) > 200:
                chunks.append(chunk)
        
        print(f"  Created {len(chunks)} chunks")
        
        # Upload all chunks (these are important labels, do full upload)
        uploaded = 0
        for i, chunk in enumerate(chunks):
            try:
                response = openai_client.embeddings.create(
                    input=chunk,
                    model="text-embedding-3-small"
                )
                embedding = response.data[0].embedding
                
                # Upload to Pinecone
                filename = os.path.basename(pdf_file).replace('.pdf', '')
                index.upsert(vectors=[{
                    "id": f"pesticide-{filename}-chunk-{i}",
                    "values": embedding,
                    "metadata": {
                        "text": chunk,
                        "source": f"Pesticide Label: {filename}",
                        "type": "pesticide_label",
                        "chunk_id": i
                    }
                }])
                
                uploaded += 1
                
                if (i+1) % 20 == 0:
                    print(f"    Uploaded {i+1}/{len(chunks)} chunks")
                
            except Exception as e:
                print(f"    ✗ Error on chunk {i}: {e}")
        
        total_chunks += uploaded
        print(f"  ✓ Successfully uploaded {uploaded} chunks")
        
    except Exception as e:
        print(f"  ✗ Error: {e}")

print(f"\n{'='*60}")
print(f"UPLOAD COMPLETE")
print(f"{'='*60}")
print(f"Pesticide label chunks uploaded: {total_chunks}")
print(f"\n🌱 Your Turf AI now includes full pesticide labels!")
print(f"   Superintendents can ask about rates, diseases, REI, etc.")
print(f"{'='*60}\n")
