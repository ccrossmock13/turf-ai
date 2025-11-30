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

print("Envu (Bayer) Complete Scraper\n")
print("Scrapes product pages + PDF labels\n")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# Envu product URLs
PRODUCTS = [
    # Fungicides
    "https://www.us.envu.com/golf-course-management/golf/products/interface-stressgard",
    "https://www.us.envu.com/golf-course-management/golf/products/chipco-signature",
    "https://www.us.envu.com/golf-course-management/golf/products/26GT",
    "https://www.us.envu.com/golf-course-management/golf/products/Chipco-26019-FLO",
    "https://www.us.envu.com/golf-course-management/golf/products/exteris-stressgard",
    "https://www.us.envu.com/golf-course-management/golf/products/tartan-stressgard",
    "https://www.us.envu.com/golf-course-management/golf/products/honor-intrinsic",
    "https://www.us.envu.com/golf-course-management/golf/products/mirage-stressgard",
    "https://www.us.envu.com/golf-course-management/golf/products/banol",
    "https://www.us.envu.com/golf-course-management/golf/products/compass",
    "https://www.us.envu.com/golf-course-management/golf/products/Bayleton-FLO",
    "https://www.us.envu.com/golf-course-management/golf/products/heritage-maxx",
    "https://www.us.envu.com/golf-course-management/golf/products/densicor",
    "https://www.us.envu.com/golf-course-management/golf/products/fiata-stressgard",
    "https://www.us.envu.com/golf-course-management/golf/products/indemnify",
    "https://www.us.envu.com/golf-course-management/golf/products/resilia",
    "https://www.us.envu.com/golf-course-management/golf/products/rayora",
    "https://www.us.envu.com/golf-course-management/golf/products/honor-guard",
    
    # Herbicides
    "https://www.us.envu.com/golf-course-management/golf/products/celsius-wg",
    "https://www.us.envu.com/golf-course-management/golf/products/tribute-total",
    "https://www.us.envu.com/golf-course-management/golf/products/revolver",
    "https://www.us.envu.com/golf-course-management/golf/products/specticle-flo",
    "https://www.us.envu.com/golf-course-management/golf/products/specticle-g",
    "https://www.us.envu.com/golf-course-management/golf/products/acclaim-extra",
    "https://www.us.envu.com/golf-course-management/golf/products/certainty-turf",
    "https://www.us.envu.com/golf-course-management/golf/products/image",
    "https://www.us.envu.com/golf-course-management/golf/products/solitare",
    "https://www.us.envu.com/golf-course-management/golf/products/prograss-ec",
    "https://www.us.envu.com/golf-course-management/golf/products/ronstar-flo",
    "https://www.us.envu.com/golf-course-management/golf/products/sencor",
    
    # Insecticides
    "https://www.us.envu.com/golf-course-management/golf/products/merit",
    "https://www.us.envu.com/golf-course-management/golf/products/Chipco-Choice",
    "https://www.us.envu.com/golf-course-management/golf/products/topchoice",
    "https://www.us.envu.com/golf-course-management/golf/products/tetrino",
    "https://www.us.envu.com/golf-course-management/golf/products/allectus-sc",
    "https://www.us.envu.com/golf-course-management/golf/products/dylox",
    
    # Plant Growth Regulators
    "https://www.us.envu.com/golf-course-management/golf/products/proxy",
    "https://www.us.envu.com/golf-course-management/golf/products/cutless-50w",
    "https://www.us.envu.com/golf-course-management/golf/products/tnex",
]

def extract_pdf_text(pdf_url):
    """Download and extract text from FULL PDF label"""
    try:
        response = requests.get(pdf_url, timeout=30)
        if response.status_code == 200:
            pdf_file = BytesIO(response.content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text() + "\n"
            
            return text
        return ""
    except Exception as e:
        print(f"    Error extracting PDF: {e}")
        return ""

def scrape_envu_product(url):
    """Scrape product page and find label PDF"""
    try:
        print(f"\nScraping: {url}")
        driver.get(url)
        time.sleep(4)
        
        # Dismiss cookie banner
        try:
            driver.execute_script("document.querySelector('.cookie-banner')?.remove()")
        except:
            pass
        
        # Get product name from URL
        product_name = url.split('/')[-1].replace('-', ' ').title()
        
        # Get page text
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        
        # Extract description
        description = ""
        lines = page_text.split('\n')
        for line in lines:
            if len(line) > 50 and any(word in line.lower() for word in ['fungicide', 'herbicide', 'insecticide', 'controls', 'provides']):
                description = line
                break
        
        # Extract active ingredient
        active_ingredient = ""
        for line in lines:
            if 'active ingredient' in line.lower():
                active_ingredient = line
                break
        
        # Find label PDF in page source
        label_url = None
        try:
            page_source = driver.page_source
            pdf_matches = re.findall(r'(https?://[^\s"]+\.pdf)', page_source)
            if pdf_matches:
                # Look for label/SDS PDF
                for pdf in pdf_matches:
                    if any(word in pdf.lower() for word in ['label', 'specimen', 'product']):
                        label_url = pdf
                        print(f"  Found label PDF: {label_url}")
                        break
                if not label_url and pdf_matches:
                    label_url = pdf_matches[0]
                    print(f"  Found PDF: {label_url}")
        except Exception as e:
            print(f"  Could not find label PDF: {e}")
        
        # Extract PDF text if found
        label_text = ""
        if label_url:
            print(f"  Extracting label text...")
            label_text = extract_pdf_text(label_url)
        
        # Build complete product text
        product_text = f"Product Name: {product_name}\n"
        product_text += f"Brand: Envu (formerly Bayer)\n"
        
        if 'fungicide' in url:
            product_text += "Type: Fungicide\n"
        elif 'herbicide' in url or any(x in url for x in ['celsius', 'tribute', 'revolver', 'specticle']):
            product_text += "Type: Herbicide\n"
        elif 'insecticide' in url or any(x in url for x in ['merit', 'chipco-choice', 'topchoice', 'tetrino']):
            product_text += "Type: Insecticide\n"
        elif any(x in url for x in ['proxy', 'cutless', 'tnex']):
            product_text += "Type: Plant Growth Regulator\n"
        
        product_text += "\n"
        
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
    for i, url in enumerate(PRODUCTS):
        # Restart browser every 10 products to prevent crashes
        if i > 0 and i % 10 == 0:
            print(f"\n  Restarting browser...")
            driver.quit()
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            time.sleep(2)
        
        product = scrape_envu_product(url)
        if product and len(product['text']) > 200:
            products.append(product)
            print(f"  ✓ {product['name']}")
        else:
            print(f"  ⚠️  Insufficient data")
        
        time.sleep(2)
    
    driver.quit()
    
    print(f"\n{'='*70}")
    print(f"Scraped {len(products)} products")
    print(f"{'='*70}\n")
    
    # Upload to Pinecone with smart chunking
    print("Uploading to Pinecone...\n")
    
    uploaded = 0
    for product in products:
        try:
            label_text = product['text']
            
            # If label text is huge, split into multiple chunks
            if len(label_text) > 7000:
                parts = label_text.split("Label Information:")
                base_info = parts[0]
                
                if len(parts) > 1:
                    full_label = parts[1]
                    label_chunks = [full_label[i:i+6000] for i in range(0, len(full_label), 6000)]
                    
                    # Upload base info + first label chunk
                    chunk1_text = base_info + "Label Information:\n" + label_chunks[0]
                    
                    response = openai_client.embeddings.create(
                        input=chunk1_text,
                        model="text-embedding-3-small"
                    )
                    embedding = response.data[0].embedding
                    
                    safe_name = re.sub(r'[^a-z0-9]+', '-', product['name'].lower()).strip('-')
                    product_id = f"envu-{safe_name}"
                    
                    index.upsert(vectors=[{
                        "id": product_id,
                        "values": embedding,
                        "metadata": {
                            "text": chunk1_text,
                            "source": f"Envu - {product['name']}",
                            "type": "pesticide_product",
                            "brand": "Envu",
                            "product_name": product['name'],
                            "url": product['url']
                        }
                    }])
                    
                    uploaded += 1
                    
                    # Upload additional label chunks
                    for i, chunk in enumerate(label_chunks[1:], start=2):
                        chunk_text = f"Product Name: {product['name']} (Label Section {i})\nBrand: Envu\n\n{chunk}"
                        
                        response = openai_client.embeddings.create(
                            input=chunk_text,
                            model="text-embedding-3-small"
                        )
                        embedding = response.data[0].embedding
                        
                        index.upsert(vectors=[{
                            "id": f"envu-{safe_name}-label-{i}",
                            "values": embedding,
                            "metadata": {
                                "text": chunk_text,
                                "source": f"Envu - {product['name']} (Label Section {i})",
                                "type": "pesticide_product",
                                "brand": "Envu",
                                "product_name": product['name']
                            }
                        }])
                        
                        uploaded += 1
                else:
                    # No label, upload base only
                    response = openai_client.embeddings.create(
                        input=label_text,
                        model="text-embedding-3-small"
                    )
                    embedding = response.data[0].embedding
                    
                    safe_name = re.sub(r'[^a-z0-9]+', '-', product['name'].lower()).strip('-')
                    
                    index.upsert(vectors=[{
                        "id": f"envu-{safe_name}",
                        "values": embedding,
                        "metadata": {
                            "text": label_text,
                            "source": f"Envu - {product['name']}",
                            "type": "pesticide_product",
                            "brand": "Envu",
                            "product_name": product['name']
                        }
                    }])
                    
                    uploaded += 1
            else:
                # Small enough for one chunk
                response = openai_client.embeddings.create(
                    input=label_text,
                    model="text-embedding-3-small"
                )
                embedding = response.data[0].embedding
                
                safe_name = re.sub(r'[^a-z0-9]+', '-', product['name'].lower()).strip('-')
                
                index.upsert(vectors=[{
                    "id": f"envu-{safe_name}",
                    "values": embedding,
                    "metadata": {
                        "text": label_text,
                        "source": f"Envu - {product['name']}",
                        "type": "pesticide_product",
                        "brand": "Envu",
                        "product_name": product['name']
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
    print(f"Uploaded: {uploaded} chunks")
    print(f"\nYour Turf AI now has Envu/Bayer products with label data!")
    
except Exception as e:
    print(f"\nError: {e}")
    driver.quit()