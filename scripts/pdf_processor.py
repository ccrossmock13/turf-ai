import os
from pinecone import Pinecone
import openai
from dotenv import load_dotenv
import PyPDF2
import re

load_dotenv()

# Initialize
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("=" * 80)
print("IMPROVED PDF PROCESSOR")
print("=" * 80)
print("\nThis processor will:")
print("✓ Keep original filename in metadata")
print("✓ Add PDF path for clickable links")
print("✓ Create proper document names")
print("✓ Track processed files (no duplicates)")
print("✓ Smart chunking based on content\n")

# PDF folder
PDF_FOLDER = "static/pdfs"
PROCESSED_FILE = "processed_pdfs_v2.txt"

# Load already processed files
processed = set()
if os.path.exists(PROCESSED_FILE):
    with open(PROCESSED_FILE, 'r') as f:
        processed = set(line.strip() for line in f)

# Get all PDFs
pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.endswith('.pdf')]
print(f"Found {len(pdf_files)} PDFs in {PDF_FOLDER}")
print(f"Already processed: {len(processed)}")
print(f"New to process: {len([f for f in pdf_files if f not in processed])}\n")

# Let user select what to process
print("Options:")
print("1. Process all new PDFs")
print("2. Process specific PDF")
print("3. Reprocess everything (will create duplicates!)")
choice = input("\nEnter choice (1-3): ").strip()

if choice == "2":
    print("\nAvailable PDFs:")
    for i, pdf in enumerate(pdf_files[:20], 1):
        status = "✓ Processed" if pdf in processed else "○ New"
        print(f"{i}. {pdf} {status}")
    if len(pdf_files) > 20:
        print(f"... and {len(pdf_files) - 20} more")
    
    pdf_name = input("\nEnter PDF filename: ").strip()
    pdf_files = [pdf_name] if pdf_name in pdf_files else []
elif choice == "3":
    confirm = input("This will create duplicates. Are you sure? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Cancelled")
        exit()
else:
    # Process only new PDFs
    pdf_files = [f for f in pdf_files if f not in processed]

if not pdf_files:
    print("No PDFs to process")
    exit()

print(f"\nProcessing {len(pdf_files)} PDFs...\n")

def clean_filename_to_title(filename):
    """Convert filename to readable title"""
    # Remove .pdf
    name = filename.replace('.pdf', '')
    
    # Replace common separators with spaces
    name = name.replace('-', ' ').replace('_', ' ')
    
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Title case
    name = name.title()
    
    return name

def extract_text_from_pdf(filepath):
    """Extract all text from PDF"""
    try:
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
    except Exception as e:
        print(f"  Error reading PDF: {e}")
        return None

def detect_document_type(filename, text):
    """Detect what type of document this is"""
    filename_lower = filename.lower()
    text_lower = text[:2000].lower()
    
    # Check patterns
    if any(word in filename_lower for word in ['ntep', 'trial']):
        return 'ntep_trial', 'NTEP'
    elif any(word in filename_lower for word in ['usga', 'green section']):
        return 'university_extension', 'USGA'
    elif any(word in text_lower for word in ['fungicide', 'herbicide', 'insecticide', 'epa reg']):
        return 'pesticide_label', 'Product Label'
    elif any(word in filename_lower for word in ['toro', 'john deere', 'irrigation', 'mower', 'equipment']):
        return 'equipment_catalog', 'Equipment'
    elif any(word in text_lower for word in ['university', 'research', 'journal', 'abstract']):
        return 'university_extension', 'Research'
    else:
        return 'university_extension', 'Research'

def smart_chunk_text(text, chunk_size=500, overlap=50):
    """Chunk text intelligently at paragraph/sentence breaks"""
    chunks = []
    
    # Split by double newlines (paragraphs)
    paragraphs = text.split('\n\n')
    
    current_chunk = ""
    for para in paragraphs:
        # Skip if paragraph is empty
        if not para.strip():
            continue
            
        # If single paragraph is too big, split it further
        if len(para) > chunk_size:
            # Split by sentences
            sentences = re.split(r'[.!?]+\s+', para)
            for sentence in sentences:
                if len(current_chunk) + len(sentence) < chunk_size:
                    current_chunk += sentence + ". "
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence + ". "
        elif len(current_chunk) + len(para) < chunk_size:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # Safety check - if any chunk is still too big, truncate it
    safe_chunks = []
    for chunk in chunks:
        if len(chunk) > 2000:  # ~500 tokens max
            # Truncate to 2000 chars
            safe_chunks.append(chunk[:2000])
        else:
            safe_chunks.append(chunk)
    
    return safe_chunks

# Process each PDF
total_processed = 0
total_vectors = 0

for pdf_file in pdf_files:
    print(f"\n{'='*80}")
    print(f"Processing: {pdf_file}")
    print('='*80)
    
    filepath = os.path.join(PDF_FOLDER, pdf_file)
    
    # Extract text
    print("  Extracting text...")
    text = extract_text_from_pdf(filepath)
    if not text:
        continue
    
    # Generate document title from filename
    doc_title = clean_filename_to_title(pdf_file)
    print(f"  Document title: {doc_title}")
    
    # Detect type
    doc_type, type_label = detect_document_type(pdf_file, text)
    print(f"  Type: {type_label} ({doc_type})")
    
    # Create PDF path for linking
    pdf_path = f"/static/pdfs/{pdf_file}"
    print(f"  PDF path: {pdf_path}")
    
    # Chunk text
    print("  Chunking text...")
    chunks = smart_chunk_text(text)
    print(f"  Created {len(chunks)} chunks")
    
    # Upload to Pinecone
    print("  Uploading to Pinecone...")
    vectors = []
    
    for i, chunk in enumerate(chunks):
        # Get embedding
        response = openai_client.embeddings.create(
            input=chunk,
            model="text-embedding-3-small"
        )
        embedding = response.data[0].embedding
        
        # Create vector ID
        safe_filename = re.sub(r'[^a-zA-Z0-9]', '-', pdf_file.replace('.pdf', ''))
        vector_id = f"research-{safe_filename}-chunk-{i}"
        
        # Metadata
        metadata = {
            'text': chunk,
            'document_name': doc_title,
            'source': doc_title,
            'type': doc_type,
            'brand': 'Research' if doc_type == 'university_extension' else 'NTEP' if doc_type == 'ntep_trial' else 'Equipment',
            'pdf_path': pdf_path,
            'original_filename': pdf_file,
            'chunk_index': i,
            'total_chunks': len(chunks)
        }
        
        vectors.append({
            'id': vector_id,
            'values': embedding,
            'metadata': metadata
        })
        
        # Upload in batches of 100
        if len(vectors) >= 100:
            index.upsert(vectors=vectors)
            print(f"    Uploaded {len(vectors)} vectors...")
            total_vectors += len(vectors)
            vectors = []
    
    # Upload remaining
    if vectors:
        index.upsert(vectors=vectors)
        total_vectors += len(vectors)
    
    print(f"  ✓ Uploaded {len(chunks)} chunks to Pinecone")
    
    # Mark as processed
    with open(PROCESSED_FILE, 'a') as f:
        f.write(f"{pdf_file}\n")
    
    total_processed += 1

print(f"\n{'='*80}")
print(f"✅ COMPLETE!")
print(f"{'='*80}")
print(f"PDFs processed: {total_processed}")
print(f"Total vectors created: {total_vectors}")
print(f"\nAll documents now have:")
print("  ✓ Clean readable names")
print("  ✓ Clickable PDF links")
print("  ✓ Proper document types")