from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import os
import time
import json
import re
from urllib.parse import urljoin

# Configuration
START_URL = "https://www.controlsolutionsinc.com/quali-pro/products"
DOWNLOAD_FOLDER = os.path.expanduser("~/Desktop/turf-ai/static/quali-pro-labels")
TEXT_FOLDER = os.path.expanduser("~/Desktop/turf-ai/static/quali-pro-texts")

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(TEXT_FOLDER, exist_ok=True)

print("="*80)
print("PENN STATE SCRAPER (WITH JAVASCRIPT SUPPORT)")
print("="*80)
print("\nSetting up browser...\n")

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument('--headless')  # Run in background
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

# Initialize driver
driver = webdriver.Chrome(options=chrome_options)

try:
    # Step 1: Get main page
    print(f"Loading: {START_URL}")
    driver.get(START_URL)
    time.sleep(3)  # Wait for JavaScript to load
    
    # Get all links
    links = driver.find_elements(By.TAG_NAME, 'a')
    article_urls = []
    
    for link in links:
        try:
            href = link.get_attribute('href')
            if href and '/research/centers/turf/extension/' in href:
                if href not in article_urls and href != START_URL:
                    article_urls.append(href)
        except:
            continue
    
    print(f"Found {len(article_urls)} pages to check\n")
    
    pdfs_downloaded = 0
    articles_saved = 0
    failed = []
    
    # Step 2: Visit each page
    for i, url in enumerate(article_urls, 1):
        print(f"[{i}/{len(article_urls)}] {url}")
        
        try:
            driver.get(url)
            
            # Wait for content to load (up to 10 seconds)
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.field--name-body, article, main"))
                )
            except:
                pass  # Continue anyway
            
            time.sleep(3)  # Extra wait for dynamic content
            
            # Get page source after JavaScript loads
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Get title
            try:
                title = driver.find_element(By.TAG_NAME, 'h1').text.strip()
            except:
                title = f"Article {i}"
            
            # Skip if title is empty or generic
            if not title or title == "Article" or len(title) < 3:
                print(f"  ✗ Invalid title, skipping")
                failed.append(url)
                continue
            
            clean_title = re.sub(r'[^\w\s-]', '', title)
            clean_title = re.sub(r'[-\s]+', '-', clean_title)[:100]
            
            # Look for PDF link
            pdf_link = None
            try:
                pdf_links = driver.find_elements(By.XPATH, "//a[contains(@href, '.pdf')]")
                if pdf_links:
                    pdf_link = pdf_links[0].get_attribute('href')
            except:
                pass
            
            if pdf_link:
                print(f"  ✓ PDF found")
                import requests
                pdf_response = requests.get(pdf_link)
                filepath = os.path.join(DOWNLOAD_FOLDER, clean_title + '.pdf')
                with open(filepath, 'wb') as f:
                    f.write(pdf_response.content)
                print(f"  ✓ Downloaded: {clean_title}.pdf")
                pdfs_downloaded += 1
                
            else:
                # Extract article text - try multiple methods
                content = None
                
                # Method 1: Try CSS selectors
                selectors = [
                    'div.field--name-body',
                    'div.field-item',
                    'div.content',
                    'article .content',
                    'main',
                ]
                
                for selector in selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements and len(elements[0].text) > 200:
                            content = elements[0].text
                            print(f"  ℹ Found content with: {selector}")
                            break
                    except:
                        continue
                
                # Method 2: Get all paragraphs if selectors fail
                if not content:
                    try:
                        paragraphs = driver.find_elements(By.TAG_NAME, 'p')
                        text_parts = [p.text for p in paragraphs if len(p.text) > 20]
                        content = '\n\n'.join(text_parts)
                        if len(content) > 200:
                            print(f"  ℹ Extracted from paragraphs")
                    except:
                        pass
                
                if content and len(content) > 200:
                    # Clean up
                    content = content.replace("JavaScript seems to be disabled in your browser.", "")
                    content = content.replace("For the best experience on our site, be sure to turn on Javascript in your browser.", "")
                    content = content.strip()
                    
                    if len(content) > 200:
                        article_data = {
                            'title': title,
                            'url': url,
                            'source': 'Penn State Extension',
                            'text': content,
                            'type': 'university_extension'
                        }
                        
                        filepath = os.path.join(TEXT_FOLDER, clean_title + '.json')
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(article_data, f, indent=2)
                        
                        print(f"  ✓ Saved article: {clean_title}.json ({len(content)} chars)")
                        articles_saved += 1
                    else:
                        print(f"  ✗ Content too short after cleanup")
                        failed.append(url)
                else:
                    print(f"  ✗ No content found (tried all methods)")
                    failed.append(url)
            
            time.sleep(2)  # Be nice to the server
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed.append(url)
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}\n")
    print(f"Pages checked: {len(article_urls)}")
    print(f"PDFs downloaded: {pdfs_downloaded}")
    print(f"Articles saved: {articles_saved}")
    print(f"Failed: {len(failed)}")
    
    if pdfs_downloaded > 0:
        print(f"\n✅ PDFs: {DOWNLOAD_FOLDER}")
    if articles_saved > 0:
        print(f"✅ Articles: {TEXT_FOLDER}")

finally:
    driver.quit()
    print("\n✅ Browser closed")