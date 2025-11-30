from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import os
import time
import re
import requests

# Configuration
START_URL = "https://www.controlsolutionsinc.com/quali-pro/products?product_type=Fungicides"
DOWNLOAD_FOLDER = os.path.expanduser("~/Desktop/turf-ai/static/product-labels")

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

print("="*80)
print("CONTROL SOLUTIONS INC LABEL SCRAPER")
print("="*80)
print(f"\nDownloading to: {DOWNLOAD_FOLDER}\n")

# Setup Chrome
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=chrome_options)

try:
    print(f"Loading: {START_URL}")
    driver.get(START_URL)
    time.sleep(5)
    
    print(f"Page title: {driver.title}")
    print(f"Extracting labels from main page...\n")
    
    # Get page source
    page_source = driver.page_source
    
    # Find all S3 label PDFs in page source
    import re
    all_s3_pdfs = re.findall(r'https://s3-us-west-1\.amazonaws\.com/agrian-cg-fs1-production/pdfs/[^"\']+\.pdf', page_source)
    
    # Filter for labels only (exclude MSDS/SDS)
    label_urls = []
    seen_products = set()
    
    for pdf_url in all_s3_pdfs:
        pdf_lower = pdf_url.lower()
        
        # Skip MSDS/SDS
        if 'msds' in pdf_lower or 'sds' in pdf_lower:
            continue
        
        # Only keep labels
        if 'label' in pdf_lower:
            # Extract product name from filename
            filename = pdf_url.split('/')[-1]
            product_base = filename.replace('_Label.pdf', '').replace('_Labeldry.pdf', '')
            
            # Avoid duplicates
            if product_base not in seen_products:
                label_urls.append((product_base, pdf_url))
                seen_products.add(product_base)
    
    print(f"Found {len(label_urls)} product labels\n")
    
    downloaded = 0
    failed = []
    
    for i, (product_name, label_url) in enumerate(label_urls, 1):
        print(f"[{i}/{len(label_urls)}] {product_name}")
        
        try:
            # Download label
            response = requests.get(label_url, timeout=30)
            
            # Clean filename
            clean_name = re.sub(r'[^\w\s-]', '', product_name)
            clean_name = re.sub(r'[-\s]+', '-', clean_name)
            filename = clean_name + '-Label.pdf'
            
            filepath = os.path.join(DOWNLOAD_FOLDER, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"  ✓ Downloaded: {filename}")
            downloaded += 1
            
            time.sleep(0.5)  # Be nice to server
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed.append(label_url)
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed.append(product_url)
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}\n")
    print(f"Labels found: {len(label_urls)}")
    print(f"Downloaded: {downloaded}")
    print(f"Failed: {len(failed)}")
    
    if downloaded > 0:
        print(f"\n✅ Labels saved to: {DOWNLOAD_FOLDER}")
        print(f"   Next: python improved_pdf_processor.py")
    
    if failed and len(failed) <= 10:
        print(f"\nFailed URLs:")
        for url in failed:
            print(f"  - {url}")

finally:
    driver.quit()
    print("\n✅ Browser closed")