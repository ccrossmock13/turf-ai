import openai
from pinecone import Pinecone
import os
from dotenv import load_dotenv
import json

load_dotenv()

# Initialize
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

ARTICLES_FOLDER = os.path.expanduser("~/Desktop/turf-ai/static/penn-state-articles")

def chunk_text(text, chunk_size=600, overlap=100):
    """Split text into overlapping chunks by characters, not words"""
    chunks = []
    
    # Split by paragraphs first
    paragraphs = text.split('\n\n')
    
    current_chunk = ""
    
    for para in paragraphs:
        # If adding this paragraph would exceed chunk size, save current chunk
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            # Start new chunk with overlap from end of previous
            current_chunk = current_chunk[-overlap:] + "\n\n" + para
        else:
            current_chunk += "\n\n" + para if current_chunk else para
    
    # Add final chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # If we only got 1 chunk and it's very long, force split it
    if len(chunks) == 1 and len(chunks[0]) > chunk_size * 2:
        text = chunks[0]
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size]
            if chunk.strip():
                chunks.append(chunk.strip())
    
    # SAFETY: If any chunk is still too long (>3000 chars = ~2000 tokens), force split
    safe_chunks = []
    for chunk in chunks:
        if len(chunk) > 3000:
            # Force split long chunks
            for i in range(0, len(chunk), 2500):
                safe_chunks.append(chunk[i:i+2500])
        else:
            safe_chunks.append(chunk)
    
    return safe_chunks

print("="*80)
print("PENN STATE ARTICLE PROCESSOR")
print("="*80)
print(f"\nProcessing articles from: {ARTICLES_FOLDER}\n")

# Get all JSON files
article_files = [f for f in os.listdir(ARTICLES_FOLDER) if f.endswith('.json')]

if not article_files:
    print("No article files found!")
    exit()

print(f"Found {len(article_files)} articles to process\n")

# Check what's already in Pinecone to avoid duplicates
print("Checking for already processed articles...")
try:
    # Query to get all existing Penn State articles
    existing_results = index.query(
        vector=[0.0] * 1536,
        top_k=10000,
        include_metadata=True
    )
    
    existing_sources = set()
    for match in existing_results['matches']:
        source = match['metadata'].get('source', '')
        if 'penn' in source.lower() or 'state' in source.lower():
            existing_sources.add(source)
    
    print(f"Found {len(existing_sources)} existing Penn State articles in database\n")
except Exception as e:
    print(f"Could not check existing articles: {e}\n")
    existing_sources = set()

total_chunks = 0
total_cost = 0
skipped = 0

for i, filename in enumerate(article_files, 1):
    filepath = os.path.join(ARTICLES_FOLDER, filename)
    
    print(f"[{i}/{len(article_files)}] Processing: {filename}")
    
    try:
        # Load article data
        with open(filepath, 'r', encoding='utf-8') as f:
            article = json.load(f)
        
        title = article['title']
        text = article['text']
        url = article['url']
        
        # Skip if already processed
        if title in existing_sources:
            print(f"  ⏭️  Already processed, skipping")
            skipped += 1
            continue
        
        # Skip if too short
        if len(text) < 100:
            print(f"  ⚠ Skipping - too short ({len(text)} chars)")
            skipped += 1
            continue
        
        # Chunk the text
        chunks = chunk_text(text)
        print(f"  → Created {len(chunks)} chunks")
        
        # Process each chunk
        vectors = []
        for chunk_idx, chunk in enumerate(chunks):
            # Create embedding
            response = openai_client.embeddings.create(
                input=chunk,
                model="text-embedding-3-small"
            )
            
            embedding = response.data[0].embedding
            
            # Create vector ID
            vector_id = f"penn-state-{filename.replace('.json', '')}-chunk-{chunk_idx}"
            
            # Metadata
            metadata = {
                'text': chunk,
                'source': title,
                'document_name': title,
                'type': 'university_extension',
                'url': url,
                'chunk_index': chunk_idx,
                'total_chunks': len(chunks)
            }
            
            vectors.append({
                'id': vector_id,
                'values': embedding,
                'metadata': metadata
            })
            
            # Estimate cost
            total_cost += len(chunk.split()) * 0.00002 / 1000  # $0.02 per 1M tokens
        
        # Upload to Pinecone in batches
        batch_size = 100
        for j in range(0, len(vectors), batch_size):
            batch = vectors[j:j+batch_size]
            index.upsert(vectors=batch)
        
        print(f"  ✓ Uploaded {len(vectors)} chunks to Pinecone")
        total_chunks += len(vectors)
        
    except Exception as e:
        print(f"  ✗ Error: {e}")

# Summary
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}\n")
print(f"Articles found: {len(article_files)}")
print(f"Already processed: {skipped}")
print(f"Newly processed: {len(article_files) - skipped}")
print(f"Total chunks uploaded: {total_chunks}")
print(f"Estimated cost: ${total_cost:.4f}")
print(f"\n✅ Penn State articles added to Pinecone!")