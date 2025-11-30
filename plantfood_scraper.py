from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import openai
from pinecone import Pinecone
import os
from dotenv import load_dotenv

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

print("Plant Food Company Complete Scraper\n")
print("Initializing browser...")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# All product URLs
URLS = {
    "Biostimulants": [
        "https://www.plantfoodco.com/golf-professional-turf/products/biostimulants/impulse-green-t/",
        "https://www.plantfoodco.com/golf-professional-turf/products/biostimulants/kelplant-1-0-1/",
        "https://www.plantfoodco.com/golf-professional-turf/products/biostimulants/omega-x34/",
        "https://www.plantfoodco.com/golf-professional-turf/products/biostimulants/humic-acid-19/",
    ],
    "Liquid Fertilizer": [
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/0-0-25-potassium-plus-17-sulfur/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/polyphosphite-30/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/0-0-29-infiltrate-k/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/2-20-22-dkp-xtra/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/7-0-0-8-sulfur/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/7-0-7-20-sulfur-plus/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/8-16-8-2-sulfur/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/8-27-5-healthy-start/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/10-2-4-sulfur-micros/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/10-2-10-50srn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/10-4-6-sulfur-micros/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/10-10-10-sulfur-micros/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/10-34-0/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/12-0-12-50-srn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/12-3-12-50-srn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/12-3-12-50-srn-synergy/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/16-0-8-50-srn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/16-2-5-25-srn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/16-2-7-25-srn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/16-2-8-50-srn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/18-3-3-green-t/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/18-3-4-super-mk/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/18-3-6-50-srn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/20-0-0-50-srn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/20-3-3-20srn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/26-1-4-75-msn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/28-0-0-72-srn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/29-0-0-50-srn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/30-0-0-uan/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/30-0-0-60-srn/",
        "https://www.plantfoodco.com/golf-professional-turf/products/liquid-fertilizer/30-0-0-90-msn/",
    ],
    "Secondary Nutrients": [
        "https://www.plantfoodco.com/golf-professional-turf/products/secondary-nutrients/sugar-cal-10-calcium-chelate/",
        "https://www.plantfoodco.com/golf-professional-turf/products/secondary-nutrients/cal-nitrate-9-0-0/",
        "https://www.plantfoodco.com/golf-professional-turf/products/secondary-nutrients/calcium-thiosulfate/",
    ],
    "Fungicides": [
        "https://www.plantfoodco.com/golf-professional-turf/products/fungicides/kphite-7lp/",
    ],
    "Micronutrients": [
        "https://www.plantfoodco.com/golf-professional-turf/products/micronutrients/micro-mix/",
        "https://www.plantfoodco.com/golf-professional-turf/products/micronutrients/green-t-micro-pack-edta-chelate-solution/",
        "https://www.plantfoodco.com/golf-professional-turf/products/micronutrients/manganese-5/",
        "https://www.plantfoodco.com/golf-professional-turf/products/micronutrients/iron-5/",
        "https://www.plantfoodco.com/golf-professional-turf/products/micronutrients/iron-12/",
        "https://www.plantfoodco.com/golf-professional-turf/products/micronutrients/copper-5/",
        "https://www.plantfoodco.com/golf-professional-turf/products/micronutrients/zinc-7/",
    ],
    "Wetting Agents": [
        "https://www.plantfoodco.com/golf-professional-turf/products/wetting-agents/flo-thru-plus/",
        "https://www.plantfoodco.com/golf-professional-turf/products/wetting-agents/hydration-plus/",
        "https://www.plantfoodco.com/golf-professional-turf/products/wetting-agents/regulate-plus/",
    ],
    "Turf Pigment": [
        "https://www.plantfoodco.com/golf-professional-turf/products/turf-pigment/green-lawnger/",
    ],
    "Water Treatments": [
        "https://www.plantfoodco.com/golf-professional-turf/products/water-treatments/pHusion-calcium/",
        "https://www.plantfoodco.com/golf-professional-turf/products/water-treatments/pHusion-sulfuric/",
    ],
    "Soil Amendments": [
        "https://www.plantfoodco.com/golf-professional-turf/products/soil-amendments/pHusion-lime/",
        "https://www.plantfoodco.com/golf-professional-turf/products/soil-amendments/pHusion-gypsum/",
    ],
}

total = sum(len(urls) for urls in URLS.values())
print(f"Scraping {total} products...\n")

products = []
scraped = 0

try:
    for category, urls in URLS.items():
        print(f"\n{category}: {len(urls)} products")
        
        for url in urls:
            try:
                driver.get(url)
                time.sleep(3)
                
                # Get page text
                page_text = driver.find_element(By.TAG_NAME, 'body').text
                
                # Extract product name from URL
                name = url.split('/')[-2].replace('-', ' ').title()
                
                # Parse content sections
                lines = page_text.split('\n')
                description = ""
                directions = ""
                
                # Find description (usually after product name, before "Directions")
                desc_start = False
                for i, line in enumerate(lines):
                    if name.lower() in line.lower() or 'green-t' in line.lower():
                        desc_start = True
                    elif desc_start and ('direction' in line.lower() or 'greens,' in line.lower()):
                        break
                    elif desc_start and len(line) > 50:
                        description += line + " "
                
                # Find directions
                for i, line in enumerate(lines):
                    if 'greens,' in line.lower() or 'fairways,' in line.lower():
                        directions += line + "\n"
                        # Get next few lines too
                        for j in range(i+1, min(i+10, len(lines))):
                            if len(lines[j]) > 20:
                                directions += lines[j] + "\n"
                
                # Build product text
                product_text = f"Product Name: {name}\n"
                product_text += f"Brand: Plant Food Company\n"
                product_text += f"Category: {category}\n\n"
                
                if description.strip():
                    product_text += f"Description: {description.strip()[:500]}\n\n"
                
                if directions.strip():
                    product_text += f"Application Directions:\n{directions.strip()[:800]}\n"
                
                if len(product_text) > 100:
                    products.append({
                        'name': name,
                        'category': category,
                        'text': product_text
                    })
                    scraped += 1
                    print(f"  ✓ {name}")
                else:
                    print(f"  ⚠️  {name} (insufficient data)")
                
            except Exception as e:
                print(f"  ✗ Error: {e}")
                continue
    
    driver.quit()
    
    print(f"\n{'='*70}")
    print(f"Scraped {scraped}/{total} products")
    print(f"{'='*70}\n")
    
    # Now upload to Pinecone
    print("Uploading to Pinecone...\n")
    
    uploaded = 0
    for product in products:
        try:
            response = openai_client.embeddings.create(
                input=product['text'],
                model="text-embedding-3-small"
            )
            embedding = response.data[0].embedding
            
            safe_name = re.sub(r'[^a-z0-9]+', '-', product['name'].lower()).strip('-')
            product_id = f"plantfood-{product['category'].lower().replace(' ', '-')}-{safe_name}"
            
            index.upsert(vectors=[{
                "id": product_id,
                "values": embedding,
                "metadata": {
                    "text": product['text'],
                    "source": f"Plant Food Company {product['category']} - {product['name']}",
                    "type": "fertilizer_product",
                    "category": product['category'].lower(),
                    "product_name": product['name'],
                    "brand": "Plant Food Company"
                }
            }])
            
            uploaded += 1
            if uploaded % 10 == 0:
                print(f"  Uploaded {uploaded}/{len(products)}")
                
        except Exception as e:
            print(f"  Error uploading {product['name']}: {e}")
    
    print(f"\n{'='*70}")
    print(f"✅ Complete!")
    print(f"{'='*70}")
    print(f"Scraped: {scraped} products")
    print(f"Uploaded: {uploaded} products")
    print(f"\nYour Turf AI now has Plant Food Company products!")
    
except Exception as e:
    print(f"\nError: {e}")
    driver.quit()