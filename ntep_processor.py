import os
import openai
from pinecone import Pinecone
from dotenv import load_dotenv
import PyPDF2
import re

load_dotenv()

# Initialize APIs
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("NTEP TRIAL DATA PROCESSOR\n")
print("Put all NTEP PDFs in the 'ntep_pdfs' folder\n")

# NTEP folder path
NTEP_FOLDER = "./ntep_pdfs"
PROCESSED_LOG = "./processed_ntep.txt"

# Check if folder exists
if not os.path.exists(NTEP_FOLDER):
    print(f"Creating {NTEP_FOLDER} folder...")
    os.makedirs(NTEP_FOLDER)
    print(f"Put your NTEP PDFs in the '{NTEP_FOLDER}' folder and run this script again.")
    exit()

# Load list of already processed files
processed_files = set()
if os.path.exists(PROCESSED_LOG):
    with open(PROCESSED_LOG, 'r') as f:
        processed_files = set(line.strip() for line in f.readlines())
    print(f"Found {len(processed_files)} previously processed NTEP PDFs\n")

# Get all PDFs in folder
all_pdf_files = [f for f in os.listdir(NTEP_FOLDER) if f.endswith('.pdf')]
pdf_files = [f for f in all_pdf_files if f not in processed_files]

if len(all_pdf_files) == 0:
    print(f"No PDFs found in {NTEP_FOLDER}")
    print("Add NTEP PDFs and run again.")
    exit()

if len(pdf_files) == 0:
    print(f"All {len(all_pdf_files)} NTEP PDFs have already been processed!")
    print("Add new PDFs to the folder to process them.")
    exit()

print(f"Found {len(pdf_files)} NEW NTEP PDFs to process (skipping {len(processed_files)} already processed)\n")

def extract_pdf_text(pdf_path):
    """Extract text from local PDF file"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text() + "\n"
            
            return text
    except Exception as e:
        print(f"    Error extracting: {e}")
        return ""

def detect_grass_type(filename, text):
    """Detect grass type from filename or content"""
    filename_lower = filename.lower()
    text_lower = text[:3000].lower()  # Check first 3000 chars
    
    # Check filename first (most reliable)
    # Bentgrass
    if any(term in filename_lower for term in ['bg', 'bent', 'agrostis', 'creeping-bent']):
        return "Bentgrass"
    # Bermudagrass
    elif any(term in filename_lower for term in ['bd', 'bermuda', 'cynodon', 'berm']):
        return "Bermudagrass"
    # Zoysiagrass
    elif any(term in filename_lower for term in ['zg', 'zoysia', 'zoysiagr']):
        return "Zoysiagrass"
    # St. Augustine
    elif any(term in filename_lower for term in ['sa', 'st-aug', 'staugustine', 'saint-aug', 'stenotaphrum']):
        return "St. Augustine"
    # Seashore Paspalum
    elif any(term in filename_lower for term in ['sp', 'seashore', 'paspalum', 'paspalum-vaginatum']):
        return "Seashore Paspalum"
    # Buffalograss
    elif any(term in filename_lower for term in ['buffalo', 'buffalogr', 'buchloe']):
        return "Buffalograss"
    # Warm Season Putting Green
    elif any(term in filename_lower for term in ['wspg', 'warm-season-putting', 'ws-putting']):
        return "Warm Season Putting Green"
    # Warm Season Water Use
    elif any(term in filename_lower for term in ['wswu', 'warm-season-water', 'ws-water']):
        return "Warm Season Water Use"
    # Warm Season Low Input
    elif any(term in filename_lower for term in ['wsli', 'warm-season-low', 'ws-low-input']):
        return "Warm Season Low Input"
    # Cool Season Water Use
    elif any(term in filename_lower for term in ['cswu', 'cool-season-water', 'cs-water']):
        return "Cool Season Water Use"
    # Cool Season Low Input
    elif any(term in filename_lower for term in ['csli', 'cool-season-low', 'cs-low-input']):
        return "Cool Season Low Input"
    # Kentucky Bluegrass
    elif any(term in filename_lower for term in ['kb', 'kbg', 'bluegrass', 'kentucky', 'poa-pratensis']):
        return "Kentucky Bluegrass"
    # Tall Fescue
    elif any(term in filename_lower for term in ['tf', 'tall-fescue', 'fescue-tall', 'festuca-arundinacea']):
        return "Tall Fescue"
    # Fine Fescue
    elif any(term in filename_lower for term in ['ff', 'fine-fescue', 'red-fescue', 'chewings']):
        return "Fine Fescue"
    # Perennial Ryegrass
    elif any(term in filename_lower for term in ['pr', 'perennial-rye', 'ryegrass', 'lolium', 'prg']):
        return "Perennial Ryegrass"
    
    # If not found in filename, check content
    if any(term in text_lower for term in ['bentgrass', 'agrostis stolonifera', 'creeping bent']):
        return "Bentgrass"
    elif any(term in text_lower for term in ['bermudagrass', 'cynodon dactylon']):
        return "Bermudagrass"
    elif any(term in text_lower for term in ['zoysiagrass', 'zoysia']):
        return "Zoysiagrass"
    elif any(term in text_lower for term in ['st. augustine', 'saint augustine', 'stenotaphrum secundatum']):
        return "St. Augustine"
    elif any(term in text_lower for term in ['seashore paspalum', 'paspalum vaginatum']):
        return "Seashore Paspalum"
    elif any(term in text_lower for term in ['buffalograss', 'buffalo grass', 'buchloe dactyloides']):
        return "Buffalograss"
    elif any(term in text_lower for term in ['warm season putting green', 'warm-season putting']):
        return "Warm Season Putting Green"
    elif any(term in text_lower for term in ['warm season water', 'warm-season water']):
        return "Warm Season Water Use"
    elif any(term in text_lower for term in ['warm season low input', 'warm-season low']):
        return "Warm Season Low Input"
    elif any(term in text_lower for term in ['cool season water', 'cool-season water']):
        return "Cool Season Water Use"
    elif any(term in text_lower for term in ['cool season low input', 'cool-season low']):
        return "Cool Season Low Input"
    elif any(term in text_lower for term in ['kentucky bluegrass', 'poa pratensis', 'kbg']):
        return "Kentucky Bluegrass"
    elif any(term in text_lower for term in ['tall fescue', 'festuca arundinacea']):
        return "Tall Fescue"
    elif any(term in text_lower for term in ['fine fescue', 'red fescue', 'chewings fescue']):
        return "Fine Fescue"
    elif any(term in text_lower for term in ['perennial ryegrass', 'lolium perenne']):
        return "Perennial Ryegrass"
    else:
        return "Unknown Grass Type"

# Process each PDF
print("="*70)
print("PROCESSING NTEP PDFS")
print("="*70 + "\n")

uploaded = 0
total_chunks = 0

for i, pdf_file in enumerate(pdf_files, 1):
    try:
        pdf_path = os.path.join(NTEP_FOLDER, pdf_file)
        filename = pdf_file.replace('.pdf', '')
        
        print(f"\n[{i}/{len(pdf_files)}] {pdf_file}")
        print(f"  Extracting text...")
        
        pdf_text = extract_pdf_text(pdf_path)
        
        if not pdf_text or len(pdf_text) < 500:
            print(f"  ⚠️  Extraction failed or empty")
            continue
        
        print(f"  Extracted {len(pdf_text)} characters")
        
        # Detect grass type
        grass_type = detect_grass_type(filename, pdf_text)
        print(f"  Detected: {grass_type}")
        
        # Build document text
        doc_text = f"NTEP Trial Report: {grass_type}\n"
        doc_text += f"Document: {filename}\n"
        doc_text += f"Type: Cultivar Trial Data\n\n"
        doc_text += pdf_text
        
        # NTEP-specific chunking: smaller chunks (3500 chars) to preserve cultivar details
        chunks = []
        current_chunk = ""
        
        lines = doc_text.split('\n')
        for line in lines:
            current_chunk += line + '\n'
            
            # Break at 3500 chars to keep cultivar ratings together
            if len(current_chunk) > 3500:
                chunks.append(current_chunk)
                current_chunk = ""
        
        if current_chunk:
            chunks.append(current_chunk)
        
        print(f"  Creating {len(chunks)} chunks...")
        
        for j, chunk in enumerate(chunks, start=1):
            chunk_text = f"NTEP {grass_type} Trial - {filename} (Part {j}/{len(chunks)})\n\n{chunk[:4000]}"
            
            response = openai_client.embeddings.create(
                input=chunk_text,
                model="text-embedding-3-small"
            )
            embedding = response.data[0].embedding
            
            safe_name = re.sub(r'[^a-z0-9]+', '-', filename.lower()).strip('-')[:60]
            safe_type = re.sub(r'[^a-z0-9]+', '-', grass_type.lower()).strip('-')
            
            index.upsert(vectors=[{
                "id": f"ntep-{safe_type}-{safe_name}-{j}",
                "values": embedding,
                "metadata": {
                    "text": chunk_text,
                    "source": f"NTEP {grass_type} - {filename}",
                    "type": "ntep_trial",
                    "brand": f"NTEP {grass_type}",
                    "grass_type": grass_type,
                    "document_name": filename
                }
            }])
            
            uploaded += 1
            total_chunks += 1
        
        print(f"  ✓ Uploaded {len(chunks)} chunks")
        
        # Mark as processed
        with open(PROCESSED_LOG, 'a') as f:
            f.write(f"{pdf_file}\n")
        
    except Exception as e:
        print(f"  Error: {e}")

print(f"\n{'='*70}")
print(f"✅ NTEP PROCESSING COMPLETE!")
print(f"{'='*70}")
print(f"PDFs processed: {len(pdf_files)}")
print(f"Total chunks uploaded: {total_chunks}")
print(f"\nYour Turf AI now has comprehensive NTEP trial data!")
print(f"\nProcessed files tracked in: {PROCESSED_LOG}")
print(f"\nTry asking:")
print(f"- 'What are the top rated bentgrass cultivars for dollar spot resistance?'")
print(f"- 'Compare bermudagrass cultivars for wear tolerance'")
print(f"- 'Best Kentucky bluegrass for shade tolerance according to NTEP'")
print(f"- 'Which tall fescue has highest brown patch resistance ratings?'")