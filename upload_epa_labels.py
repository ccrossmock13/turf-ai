import os
import glob
import openai
from pinecone import Pinecone
from dotenv import load_dotenv
import time

load_dotenv()

# Initialize
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

# Find all EPA label files
label_files = glob.glob("epa_labels/*.txt")

print(f"\n{'='*60}")
print(f"UPLOADING EPA LABELS TO AI DATABASE")
print(f"{'='*60}")
print(f"Found {len(label_files)} EPA label files\n")

total_chunks = 0

for idx, label_file in enumerate(label_files, 1):
    print(f"[{idx}/{len(label_files)}] Processing: {os.path.basename(label_file)}")
    
    try:
        # Read label file
        with open(label_file, 'r') as f:
            content = f.read()
        
        # Create embedding
        response = openai_client.embeddings.create(
            input=content,
            model="text-embedding-3-small"
        )
        embedding = response.data[0].embedding
        
        # Upload to Pinecone
        file_id = os.path.basename(label_file).replace('.txt', '')
        index.upsert(vectors=[{
            "id": f"epa-label-{file_id}",
            "values": embedding,
            "metadata": {
                "text": content,
                "source": f"EPA Label: {file_id}",
                "type": "pesticide_label"
            }
        }])
        
        total_chunks += 1
        print(f"  ✓ Uploaded to database")
        
    except Exception as e:
        print(f"  ✗ Error: {e}")

print(f"\n{'='*60}")
print(f"UPLOAD COMPLETE")
print(f"{'='*60}")
print(f"EPA labels uploaded: {total_chunks}")
print(f"Your Turf AI now includes pesticide label data!")
print(f"\n🌱 Total knowledge base:")
print(f"  - Research papers: 38")
print(f"  - Pesticide labels: {total_chunks}")
print(f"  - Total searchable chunks: 1068 + {total_chunks}")
print(f"{'='*60}\n")