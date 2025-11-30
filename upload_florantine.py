import openai
from pinecone import Pinecone
import os
from dotenv import load_dotenv
import re

load_dotenv()

# Initialize
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("\nUploading Floratine products with better chunking...\n")

# Read the scraped content
with open('floratine_products/all_products.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# Split by category sections
sections = content.split('=' * 60)

products = []
current_category = ""

for section in sections:
    # Detect category
    if 'FOLIAR PRODUCTS' in section:
        current_category = "Foliar"
    elif 'SOIL PRODUCTS' in section:
        current_category = "Soil"
    elif 'SPECIALTY PRODUCTS' in section:
        current_category = "Specialty"
    else:
        continue
    
    # Split into lines and find products (products typically in ALL CAPS)
    lines = section.split('\n')
    current_product = None
    product_text = []
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and noise
        if not line or 'Products' in line or '=' in line or 'VIEW' in line or 'CONTACT' in line or 'COPYRIGHT' in line:
            continue
        
        # Detect new product (all caps line that's not a keyword)
        if (line.isupper() and len(line) > 3 and 
            line not in ['PACKAGING', 'RATE', 'WEIGHT', 'BENEFITS INCLUDE:']):
            
            # Save previous product
            if current_product and product_text:
                full_text = f"PRODUCT: {current_product}\nCATEGORY: Floratine {current_category}\n\n" + '\n'.join(product_text)
                if len(full_text) > 100:  # Only save if substantial
                    products.append({
                        'name': current_product,
                        'category': current_category,
                        'text': full_text
                    })
            
            # Start new product
            current_product = line
            product_text = []
        
        elif current_product:
            product_text.append(line)
    
    # Save last product in section
    if current_product and product_text:
        full_text = f"PRODUCT: {current_product}\nCATEGORY: Floratine {current_category}\n\n" + '\n'.join(product_text)
        if len(full_text) > 100:
            products.append({
                'name': current_product,
                'category': current_category,
                'text': full_text
            })

print(f"Found {len(products)} products\n")

# Upload each product as its own chunk
uploaded = 0
for product in products:
    try:
        response = openai_client.embeddings.create(
            input=product['text'],
            model="text-embedding-3-small"
        )
        embedding = response.data[0].embedding
        
        # Create clean ID
        safe_name = re.sub(r'[^a-z0-9]+', '-', product['name'].lower()).strip('-')
        product_id = f"floratine-{product['category'].lower()}-{safe_name}"
        
        index.upsert(vectors=[{
            "id": product_id,
            "values": embedding,
            "metadata": {
                "text": product['text'],
                "source": f"Floratine {product['category']} - {product['name']}",
                "type": "fertilizer_product",
                "category": product['category'].lower(),
                "product_name": product['name']
            }
        }])
        
        uploaded += 1
        if uploaded % 10 == 0:
            print(f"  Uploaded {uploaded}/{len(products)}")
            
    except Exception as e:
        print(f"  Error on {product['name']}: {e}")

print(f"\n✓ Uploaded {uploaded} products with full context preserved")