from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time
import re
import requests
import openai
from pinecone import Pinecone
import os
from dotenv import load_dotenv
import PyPDF2
from io import BytesIO

load_dotenv()

# Initialize APIs
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

# Setup Chrome
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

print("Syngenta GreenCast Complete Scraper\n")
print("Scrapes product pages + PDF labels\n")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# Comprehensive list of Syngenta turf products
# (Manually compiled from greencastonline.com)
PRODUCTS = [
    # Herbicides
    "https://www.greencastonline.com/products/barricade-4fl-herbicide/turf",
    "https://www.greencastonline.com/products/barricade-65wg-herbicide/turf",
    "https://www.greencastonline.com/products/monument-75wx-herbicide/turf",
    "https://www.greencastonline.com/products/tenacity-herbicide/turf",
    "https://www.greencastonline.com/products/certainty-turf-herbicide/turf",
    "https://www.greencastonline.com/products/tribute-total-herbicide/turf",
    "https://www.greencastonline.com/products/fusilade-ii-turf-and-ornamental-herbicide/turf",
    "https://www.greencastonline.com/products/recognition-herbicide/turf",
    "https://www.greencastonline.com/products/reward-landscape-and-aquatic-herbicide/turf",
    "https://www.greencastonline.com/products/ronstar-50wp-herbicide/turf",
    "https://www.greencastonline.com/products/drive-xlr8-herbicide/turf",
    "https://www.greencastonline.com/products/echelon-herbicide/turf",
    
    # Fungicides
    "https://www.greencastonline.com/products/heritage-action-fungicide/turf",
    "https://www.greencastonline.com/products/heritage-fungicide/turf",
    "https://www.greencastonline.com/products/daconil-action-fungicide/turf",
    "https://www.greencastonline.com/products/daconil-ultrex-fungicide/turf",
    "https://www.greencastonline.com/products/daconil-weatherstik-fungicide/turf",
    "https://www.greencastonline.com/products/secure-action-fungicide/turf",
    "https://www.greencastonline.com/products/secure-fungicide/turf",
    "https://www.greencastonline.com/products/banner-maxx-ii-fungicide/turf",
    "https://www.greencastonline.com/products/concert-ii-fungicide/turf",
    "https://www.greencastonline.com/products/instrata-fungicide/turf",
    "https://www.greencastonline.com/products/headway-fungicide/turf",
    "https://www.greencastonline.com/products/headway-g-granular-fungicide/turf",
    "https://www.greencastonline.com/products/lexicon-intrinsic-fungicide/turf",
    "https://www.greencastonline.com/products/reserve-fungicide/turf",
    "https://www.greencastonline.com/products/briskway-fungicide/turf",
    "https://www.greencastonline.com/products/posterity-fungicide/turf",
    "https://www.greencastonline.com/products/posterity-at-fungicide/turf",
    "https://www.greencastonline.com/products/trinity-fungicide/turf",
    "https://www.greencastonline.com/products/renown-fungicide/turf",
    "https://www.greencastonline.com/products/interface-stressgard-fungicide/turf",
    "https://www.greencastonline.com/products/medallion-sc-fungicide/turf",
    "https://www.greencastonline.com/products/subdue-maxx-fungicide/turf",
    
    # Insecticides
    "https://www.greencastonline.com/products/acelepryn-insecticide/turf",
    "https://www.greencastonline.com/products/acelepryn-xtra-insecticide/turf",
    "https://www.greencastonline.com/products/renstar-insecticide/turf",
    "https://www.greencastonline.com/products/mainspring-gnl-insecticide/turf",
    "https://www.greencastonline.com/products/mallet-75wsp-insecticide/turf",
    "https://www.greencastonline.com/products/meridian-25wg-insecticide/turf",
    
    # Plant Growth Regulators
    "https://www.greencastonline.com/products/trimmit-2sc-plant-growth-regulator/turf",
    "https://www.greencastonline.com/products/primo-maxx-plant-growth-regulator/turf",
    "https://www.greencastonline.com/products/anuew-plant-growth-regulator/turf",
    
    # Specialty Products
    "https://www.greencastonline.com/products/surflan-as-specialty-herbicide/turf",
    "https://www.greencastonline.com/products/casoron-4g-specialty-herbicide/turf",
]

print(f"Scraping {len(PRODUCTS)} Syngenta turf products...\n")

def extract_pdf_text(pdf_url):
    """Download and extract text from FULL PDF label"""
    try:
        response = requests.get(pdf_url, timeout=30)
        if response.status_code == 200:
            pdf_file = BytesIO(response.content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            # Extract ALL pages from the label
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text() + "\n"
            
            return text  # Return full label text
        return ""
    except Exception as e:
        print(f"    Error extracting PDF: {e}")
        return ""

def scrape_syngenta_product(url):
    """Scrape product page and find label PDF"""
    try:
        print(f"\nScraping: {url}")
        driver.get(url)
        time.sleep(4)
        
        # Dismiss any alerts
        try:
            driver.switch_to.alert.dismiss()
        except:
            pass
        
        # Get product name from URL
        product_name = url.split('/')[-2].replace('-', ' ').title()
        
        # Get page text
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        
        # Extract description
        description = ""
        lines = page_text.split('\n')
        for i, line in enumerate(lines):
            if len(line) > 50 and 'herbicide' in line.lower() or 'fungicide' in line.lower():
                description = line
                break
        
        # Find label link
        label_url = None
        try:
            # Look for label page link
            label_slug = url.split('/')[-2]  # e.g., "barricade-4fl-herbicide"
            label_url_base = label_slug.replace('-herbicide', '').replace('-fungicide', '').replace('-insecticide', '').replace('-plant-growth-regulator', '')
            label_page = f"https://www.greencastonline.com/labels/{label_url_base}"
            
            # Visit label page to find PDF
            driver.get(label_page)
            time.sleep(3)
            
            # Dismiss any alerts
            try:
                driver.switch_to.alert.dismiss()
                time.sleep(1)
            except:
                pass
            
            # Find PDF link in page source (more reliable than clicking)
            page_source = driver.page_source
            import re
            pdf_matches = re.findall(r'(https?://[^\s"]+\.pdf)', page_source)
            if pdf_matches:
                label_url = pdf_matches[0]
                print(f"  Found label PDF: {label_url}")
            else:
                # Try alternative - look for label in metadata
                print(f"  No PDF found, checking alternate locations...")
        except Exception as e:
            print(f"  Could not find label PDF: {e}")
        
        # Extract PDF text if found
        label_text = ""
        if label_url:
            print(f"  Extracting label text...")
            label_text = extract_pdf_text(label_url)
        
        # Get active ingredient from page
        active_ingredient = ""
        for line in lines:
            if 'active ingredient' in line.lower():
                active_ingredient = line
                break
        
        # Build complete product text
        product_text = f"Product Name: {product_name}\n"
        product_text += f"Brand: Syngenta\n"
        product_text += f"Type: {'Herbicide' if 'herbicide' in url else 'Fungicide'}\n\n"
        
        if active_ingredient:
            product_text += f"Active Ingredient: {active_ingredient}\n\n"
        
        if description:
            product_text += f"Description: {description}\n\n"
        
        if label_text:
            product_text += f"Label Information:\n{label_text}\n"
        
        return {
            'name': product_name,
            'text': product_text,
            'url': url,
            'label_url': label_url
        }
        
    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None

# Main scraping loop
products = []
print(f"Starting scrape of {len(PRODUCTS)} products...\n")

try:
    for url in PRODUCTS:
        product = scrape_syngenta_product(url)
        if product and len(product['text']) > 200:
            products.append(product)
            print(f"  ✓ {product['name']}")
        else:
            print(f"  ⚠️  Insufficient data")
        
        time.sleep(2)  # Be nice to server
    
    driver.quit()
    
    print(f"\n{'='*70}")
    print(f"Scraped {len(products)} products")
    print(f"{'='*70}\n")
    
    # Upload to Pinecone
    print("Uploading to Pinecone...\n")
    
    uploaded = 0
    for product in products:
        try:
            # If label text is huge, split into multiple chunks
            label_text = product['text']
            
            # If product text > 7000 chars, split it intelligently
            if len(label_text) > 7000:
                # Split into product info + label chunks
                parts = label_text.split("Label Information:")
                base_info = parts[0]
                
                if len(parts) > 1:
                    full_label = parts[1]
                    # Chunk label by ~6000 char sections
                    label_chunks = [full_label[i:i+6000] for i in range(0, len(full_label), 6000)]
                    
                    # Upload base info + first label chunk together
                    chunk1_text = base_info + "Label Information:\n" + label_chunks[0]
                    
                    response = openai_client.embeddings.create(
                        input=chunk1_text,
                        model="text-embedding-3-small"
                    )
                    embedding = response.data[0].embedding
                    
                    safe_name = re.sub(r'[^a-z0-9]+', '-', product['name'].lower()).strip('-')
                    product_id = f"syngenta-{safe_name}"
                    
                    index.upsert(vectors=[{
                        "id": product_id,
                        "values": embedding,
                        "metadata": {
                            "text": chunk1_text,
                            "source": f"Syngenta - {product['name']}",
                            "type": "pesticide_product",
                            "brand": "Syngenta",
                            "product_name": product['name'],
                            "url": product['url'],
                            "label_url": product.get('label_url', '')
                        }
                    }])
                    
                    uploaded += 1
                    
                    # Upload additional label chunks
                    for i, chunk in enumerate(label_chunks[1:], start=2):
                        chunk_text = f"Product Name: {product['name']} (Label Section {i})\nBrand: Syngenta\n\n{chunk}"
                        
                        response = openai_client.embeddings.create(
                            input=chunk_text,
                            model="text-embedding-3-small"
                        )
                        embedding = response.data[0].embedding
                        
                        index.upsert(vectors=[{
                            "id": f"syngenta-{safe_name}-label-{i}",
                            "values": embedding,
                            "metadata": {
                                "text": chunk_text,
                                "source": f"Syngenta - {product['name']} (Label Section {i})",
                                "type": "pesticide_product",
                                "brand": "Syngenta",
                                "product_name": product['name'],
                                "url": product['url'],
                                "label_url": product.get('label_url', '')
                            }
                        }])
                        
                        uploaded += 1
                else:
                    # No label found, upload base info only
                    response = openai_client.embeddings.create(
                        input=label_text,
                        model="text-embedding-3-small"
                    )
                    embedding = response.data[0].embedding
                    
                    safe_name = re.sub(r'[^a-z0-9]+', '-', product['name'].lower()).strip('-')
                    product_id = f"syngenta-{safe_name}"
                    
                    index.upsert(vectors=[{
                        "id": product_id,
                        "values": embedding,
                        "metadata": {
                            "text": label_text,
                            "source": f"Syngenta - {product['name']}",
                            "type": "pesticide_product",
                            "brand": "Syngenta",
                            "product_name": product['name'],
                            "url": product['url'],
                            "label_url": product.get('label_url', '')
                        }
                    }])
                    
                    uploaded += 1
            else:
                # Small enough to upload as one chunk
                response = openai_client.embeddings.create(
                    input=label_text,
                    model="text-embedding-3-small"
                )
                embedding = response.data[0].embedding
                
                safe_name = re.sub(r'[^a-z0-9]+', '-', product['name'].lower()).strip('-')
                product_id = f"syngenta-{safe_name}"
                
                index.upsert(vectors=[{
                    "id": product_id,
                    "values": embedding,
                    "metadata": {
                        "text": label_text,
                        "source": f"Syngenta - {product['name']}",
                        "type": "pesticide_product",
                        "brand": "Syngenta",
                        "product_name": product['name'],
                        "url": product['url'],
                        "label_url": product.get('label_url', '')
                    }
                }])
                
                uploaded += 1
            
            if uploaded % 10 == 0:
                print(f"  Uploaded {uploaded} chunks")
                
        except Exception as e:
            print(f"  Error uploading {product['name']}: {e}")
    
    print(f"\n{'='*70}")
    print(f"✅ Complete!")
    print(f"{'='*70}")
    print(f"Scraped: {len(products)} products")
    print(f"Uploaded: {uploaded} products")
    print(f"\nYour Turf AI now has Syngenta products with label data!")
    
except Exception as e:
    print(f"\nError: {e}")
    driver.quit()