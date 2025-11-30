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

print("BASF Direct Label Upload\n")

# BASF products with direct label URLs (from better-turf.basf.ca and betterturf.basf.us)
BASF_PRODUCTS = [
    {
        'name': 'Xzemplar Fungicide',
        'label_url': 'https://better-turf.basf.ca/content/dam/cxm/agriculture/better-turf/canada/english/label-files/BASF_Xzemplar_Label.pdf'
    },
    {
        'name': 'Maxtima Fungicide',
        'label_url': 'https://better-turf.basf.ca/content/dam/cxm/agriculture/better-turf/canada/english/label-files/BASF_Maxtima_Label.pdf'
    },
    {
        'name': 'Lexicon Intrinsic Fungicide',
        'label_url': 'https://better-turf.basf.ca/content/dam/cxm/agriculture/better-turf/canada/english/label-files/BASF_Lexicon_Label.pdf'
    },
    {
        'name': 'Insignia SC Intrinsic Fungicide',
        'label_url': 'https://better-turf.basf.ca/content/dam/cxm/agriculture/better-turf/canada/english/label-files/BASF_Insignia-SC_Label.pdf'
    },
    {
        'name': 'Emerald Fungicide',
        'label_url': 'https://better-turf.basf.ca/content/dam/cxm/agriculture/better-turf/canada/english/label-files/BASF_Emerald_Label.pdf'
    },
    {
        'name': 'Drive XLR8 Herbicide',
        'label_url': 'https://better-turf.basf.ca/content/dam/cxm/agriculture/better-turf/canada/english/label-files/BASF_Drive-XLR8_Label.pdf'
    },
    {
        'name': 'Pendulum AquaCap Herbicide',
        'label_url': 'https://better-turf.basf.ca/content/dam/cxm/agriculture/better-turf/canada/english/label-files/BASF_Pendulum-AquaCap_Label.pdf'
    },
]

def extract_pdf_text(pdf_url):
    """Download and extract text from FULL PDF label"""
    try:
        print(f"  Downloading: {pdf_url}")
        response = requests.get(pdf_url, timeout=30)
        if response.status_code == 200:
            pdf_file = BytesIO(response.content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text() + "\n"
            
            print(f"  Extracted {len(text)} characters from {len(pdf_reader.pages)} pages")
            return text
        else:
            print(f"  Failed to download (status {response.status_code})")
        return ""
    except Exception as e:
        print(f"  Error: {e}")
        return ""

print("="*70)
print("Extracting BASF Labels")
print("="*70 + "\n")

uploaded = 0
for product in BASF_PRODUCTS:
    try:
        print(f"\nProcessing: {product['name']}")
        
        label_text = extract_pdf_text(product['label_url'])
        
        if not label_text or len(label_text) < 100:
            print(f"  ⚠️  Label extraction failed or empty")
            continue
        
        # Build product text
        product_text = f"Product Name: {product['name']}\n"
        product_text += f"Brand: BASF\n\n"
        product_text += f"Label Information:\n{label_text}\n"
        
        # Smart chunking if label is huge
        if len(product_text) > 7000:
            parts = product_text.split("Label Information:")
            base_info = parts[0]
            full_label = parts[1]
            label_chunks = [full_label[i:i+6000] for i in range(0, len(full_label), 6000)]
            
            # Upload first chunk
            chunk1_text = base_info + "Label Information:\n" + label_chunks[0]
            
            response = openai_client.embeddings.create(
                input=chunk1_text,
                model="text-embedding-3-small"
            )
            embedding = response.data[0].embedding
            
            safe_name = re.sub(r'[^a-z0-9]+', '-', product['name'].lower()).strip('-')
            
            index.upsert(vectors=[{
                "id": f"basf-{safe_name}",
                "values": embedding,
                "metadata": {
                    "text": chunk1_text,
                    "source": f"BASF - {product['name']}",
                    "type": "pesticide_product",
                    "brand": "BASF",
                    "product_name": product['name'],
                    "label_url": product['label_url']
                }
            }])
            
            uploaded += 1
            
            # Upload additional chunks
            for i, chunk in enumerate(label_chunks[1:], start=2):
                chunk_text = f"Product Name: {product['name']} (Label Section {i})\nBrand: BASF\n\n{chunk}"
                
                response = openai_client.embeddings.create(
                    input=chunk_text,
                    model="text-embedding-3-small"
                )
                embedding = response.data[0].embedding
                
                index.upsert(vectors=[{
                    "id": f"basf-{safe_name}-label-{i}",
                    "values": embedding,
                    "metadata": {
                        "text": chunk_text,
                        "source": f"BASF - {product['name']} (Label Section {i})",
                        "type": "pesticide_product",
                        "brand": "BASF",
                        "product_name": product['name']
                    }
                }])
                
                uploaded += 1
            
            print(f"  ✓ Uploaded {len(label_chunks)} chunks")
        else:
            # Single chunk
            response = openai_client.embeddings.create(
                input=product_text,
                model="text-embedding-3-small"
            )
            embedding = response.data[0].embedding
            
            safe_name = re.sub(r'[^a-z0-9]+', '-', product['name'].lower()).strip('-')
            
            index.upsert(vectors=[{
                "id": f"basf-{safe_name}",
                "values": embedding,
                "metadata": {
                    "text": product_text,
                    "source": f"BASF - {product['name']}",
                    "type": "pesticide_product",
                    "brand": "BASF",
                    "product_name": product['name'],
                    "label_url": product['label_url']
                }
            }])
            
            uploaded += 1
            print(f"  ✓ Uploaded")
        
    except Exception as e:
        print(f"  Error: {e}")

print(f"\n{'='*70}")
print(f"✅ Complete!")
print(f"{'='*70}")
print(f"Products: {len(BASF_PRODUCTS)}")
print(f"Uploaded: {uploaded} chunks")
print(f"\nYour Turf AI now has major BASF products with full labels!")