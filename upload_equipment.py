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

# Find all PDFs in equipment_manuals folder
pdf_files = glob.glob("equipment_manuals/*.*")

print(f"\n{'='*60}")
print(f"UPLOADING EQUIPMENT MANUALS")
print(f"{'='*60}")
print(f"Found {len(pdf_files)} files\n")

total_chunks = 0

for idx, file_path in enumerate(pdf_files, 1):
    filename = os.path.basename(file_path)
    print(f"[{idx}/{len(pdf_files)}] Processing: {filename}")
    
    try:
        # Handle PDFs
        if file_path.lower().endswith('.pdf'):
            pdf = open(file_path, 'rb')
            pdf_reader = PyPDF2.PdfReader(pdf)
            
            full_text = ""
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    full_text += text
            
            pdf.close()
        
        # Handle PowerPoint (just skip for now, would need python-pptx)
        elif file_path.lower().endswith(('.ppt', '.pptx')):
            print(f"  ⚠ PowerPoint files not supported yet, skipping")
            continue
        
        else:
            print(f"  ⚠ Unsupported file type, skipping")
            continue
        
        if len(full_text) < 500:
            print(f"  ⚠ Insufficient text extracted, skipping")
            continue
        
        print(f"  Extracted {len(full_text):,} characters")
        
        # Split into chunks
        chunk_size = 1000
        chunks = []
        for i in range(0, len(full_text), chunk_size):
            chunk = full_text[i:i+chunk_size]
            if len(chunk) > 200:
                chunks.append(chunk)
        
        print(f"  Created {len(chunks)} chunks")
        
        # Upload all chunks
        uploaded = 0
        for i, chunk in enumerate(chunks):
            try:
                response = openai_client.embeddings.create(
                    input=chunk,
                    model="text-embedding-3-small"
                )
                embedding = response.data[0].embedding
                
                clean_filename = filename.replace('.pdf', '').replace(' ', '-')
                index.upsert(vectors=[{
                    "id": f"equipment-{clean_filename}-chunk-{i}",
                    "values": embedding,
                    "metadata": {
                        "text": chunk,
                        "source": f"Equipment Manual: {filename}",
                        "type": "equipment_manual",
                        "chunk_id": i
                    }
                }])
                
                uploaded += 1
                
                if (i+1) % 20 == 0:
                    print(f"    Uploaded {i+1}/{len(chunks)} chunks")
                
            except Exception as e:
                print(f"    ✗ Error on chunk {i}: {e}")
        
        total_chunks += uploaded
        print(f"  ✓ Uploaded {uploaded} chunks")
        
    except Exception as e:
        print(f"  ✗ Error: {e}")

print(f"\n{'='*60}")
print(f"UPLOAD COMPLETE")
print(f"{'='*60}")
print(f"Equipment manual chunks uploaded: {total_chunks}")
print(f"\n🌱 Your Turf AI now includes equipment manuals!")
print(f"   Ask about sprinkler specs, mower settings, controller programming")
print(f"{'='*60}\n")
