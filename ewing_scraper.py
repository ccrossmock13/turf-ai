import requests
import openai
from pinecone import Pinecone
import os
from dotenv import load_dotenv
import PyPDF2
from io import BytesIO
import re

load_dotenv()

# Initialize APIs
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("EWING GOLF CATALOG SCRAPER\n")
print("Downloading and processing full Ewing Golf catalog...\n")

# Ewing catalog URL
EWING_CATALOG_URL = "https://20200354.fs1.hubspotusercontent-na1.net/hubfs/20200354/downloads/Ewing-Golf-2023-online-full-pages.pdf"

def extract_pdf_text(pdf_url):
    """Download and extract text from PDF"""
    try:
        print(f"Downloading catalog from: {pdf_url}")
        response = requests.get(pdf_url, timeout=60)
        
        if response.status_code == 200:
            print(f"Downloaded {len(response.content)} bytes")
            
            pdf_file = BytesIO(response.content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            print(f"Extracting text from {len(pdf_reader.pages)} pages...")
            
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                page_text = pdf_reader.pages[page_num].extract_text()
                text += f"\n--- Page {page_num + 1} ---\n"
                text += page_text
                
                if (page_num + 1) % 50 == 0:
                    print(f"  Processed {page_num + 1} pages...")
            
            print(f"Extracted {len(text)} characters total")
            return text
        else:
            print(f"Failed to download (status {response.status_code})")
            return ""
    except Exception as e:
        print(f"Error: {e}")
        return ""

# Extract catalog
print("="*70)
print("PHASE 1: Extracting Ewing Catalog")
print("="*70 + "\n")

catalog_text = extract_pdf_text(EWING_CATALOG_URL)

if not catalog_text or len(catalog_text) < 1000:
    print("Failed to extract catalog. Exiting.")
    exit()

# Phase 2: Chunk intelligently by products/sections
print("\n" + "="*70)
print("PHASE 2: Chunking by Products and Uploading")
print("="*70 + "\n")

# Split into smaller chunks based on content patterns
# Look for product headers, part numbers, etc.
# Chunk at natural breaks (product separations)

# Strategy: Split by double line breaks or product patterns
# Keep each product/section together

# First, try to identify product sections
# Products usually have: part numbers, descriptions, specs
sections = []
current_section = ""

lines = catalog_text.split('\n')

for line in lines:
    current_section += line + '\n'
    
    # Chunk when we hit ~1000-1500 chars (one product typically)
    # OR when we see a clear product separator (part number pattern, heading, etc)
    if len(current_section) > 1000:
        # Look for good break point in next 500 chars
        if any(pattern in line.upper() for pattern in ['PART#', 'PART NUMBER', 'MODEL', 'ITEM#', 'SPECIFICATIONS']):
            sections.append(current_section.strip())
            current_section = ""
        elif len(current_section) > 1500:  # Force break at 1500
            sections.append(current_section.strip())
            current_section = ""

# Add final section
if current_section.strip():
    sections.append(current_section.strip())

# Filter out tiny sections
chunks = [s for s in sections if len(s) > 300]

print(f"Created {len(chunks)} product/section chunks")
print(f"Average chunk size: {sum(len(c) for c in chunks) // len(chunks)} characters")

# Upload to Pinecone
print("\nUploading to Pinecone...")

uploaded = 0
for i, chunk in enumerate(chunks, 1):
    try:
        # Build metadata-rich text
        doc_text = f"Source: Ewing Golf Catalog 2023\n"
        doc_text += f"Chunk: {i}/{len(chunks)}\n"
        doc_text += f"Type: Irrigation Equipment, Parts, Supplies\n\n"
        doc_text += chunk[:7000]  # Limit to 7000 chars per chunk
        
        response = openai_client.embeddings.create(
            input=doc_text,
            model="text-embedding-3-small"
        )
        embedding = response.data[0].embedding
        
        index.upsert(vectors=[{
            "id": f"ewing-catalog-chunk-{i}",
            "values": embedding,
            "metadata": {
                "text": doc_text,
                "source": f"Ewing Golf Catalog - Section {i}",
                "type": "equipment_catalog",
                "brand": "Ewing Irrigation",
                "document_name": "Ewing Golf Catalog 2023"
            }
        }])
        
        uploaded += 1
        
        if uploaded % 20 == 0:
            print(f"  Uploaded {uploaded}/{len(chunks)} chunks")
        
    except Exception as e:
        print(f"  Error uploading chunk {i}: {e}")

print(f"\n{'='*70}")
print(f"✅ Complete!")
print(f"{'='*70}")
print(f"Total sections: {len(chunks)}")
print(f"Chunks uploaded: {uploaded}")
print(f"\nYour Turf AI now has the full Ewing Golf catalog!")
print(f"Covers: Irrigation parts, sprinklers, valves, controllers, tools, supplies")