import requests
from bs4 import BeautifulSoup
import os
import time
from urllib.parse import urljoin
import re
import json

# Configuration
BASE_URL = "https://plantscience.psu.edu"
START_URL = "https://plantscience.psu.edu/research/centers/turf/extension/professional-turf"
DOWNLOAD_FOLDER = os.path.expanduser("~/Desktop/turf-ai/static/penn-state-guides")
TEXT_FOLDER = os.path.expanduser("~/Desktop/turf-ai/static/penn-state-articles")

# Create download folders
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(TEXT_FOLDER, exist_ok=True)

print("="*80)
print("PENN STATE TURF EXTENSION SCRAPER")
print("="*80)
print(f"\nPDFs saved to: {DOWNLOAD_FOLDER}")
print(f"Articles saved to: {TEXT_FOLDER}\n")

# Step 1: Get all article links from main page
print("Step 1: Getting article links from main page...")
response = requests.get(START_URL)
soup = BeautifulSoup(response.text, 'html.parser')

# Find all links that go to turf articles
article_links = []
for link in soup.find_all('a', href=True):
    href = link['href']
    # Look for links to turf extension articles
    if '/research/centers/turf/extension/' in href:
        full_url = urljoin(BASE_URL, href)
        if full_url not in article_links and full_url != START_URL:
            article_links.append(full_url)

print(f"Found {len(article_links)} article pages\n")

# Step 2: Visit each article page
pdfs_downloaded = 0
articles_saved = 0
failed = []

for i, article_url in enumerate(article_links, 1):
    print(f"[{i}/{len(article_links)}] Processing: {article_url}")
    
    try:
        # Get article page
        article_response = requests.get(article_url)
        article_soup = BeautifulSoup(article_response.text, 'html.parser')
        
        # Look for PDF download link
        pdf_link = None
        
        # Method 1: Look for explicit download links
        for link in article_soup.find_all('a', href=True):
            href = link['href']
            link_text = link.get_text().lower()
            
            # Check if it's a PDF
            if href.endswith('.pdf') or 'download' in link_text or 'pdf' in link_text:
                pdf_link = urljoin(BASE_URL, href)
                break
        
        # Method 2: Look for file field links (Drupal pattern)
        if not pdf_link:
            for link in article_soup.find_all('a', href=True):
                if '/files/' in link['href'] and link['href'].endswith('.pdf'):
                    pdf_link = urljoin(BASE_URL, link['href'])
                    break
        
        # Get article title
        title_tag = article_soup.find('h1')
        title = title_tag.get_text().strip() if title_tag else f"Article {i}"
        
        # Clean filename
        clean_title = re.sub(r'[^\w\s-]', '', title)
        clean_title = re.sub(r'[-\s]+', '-', clean_title)
        clean_title = clean_title[:100]
        
        if pdf_link:
            # Download PDF
            print(f"  ✓ Found PDF: {pdf_link}")
            
            pdf_response = requests.get(pdf_link)
            filename = clean_title + '.pdf'
            filepath = os.path.join(DOWNLOAD_FOLDER, filename)
            
            with open(filepath, 'wb') as f:
                f.write(pdf_response.content)
            
            print(f"  ✓ Downloaded PDF: {filename}")
            pdfs_downloaded += 1
            
        else:
            # No PDF - extract article text from page
            print(f"  ℹ No PDF - extracting article text")
            
            # Find main content area (common Drupal selectors)
            content = None
            
            # Try different content selectors
            selectors = [
                'div.field--name-body',
                'div.content',
                'article',
                'div.node-content',
                'div.field-item'
            ]
            
            for selector in selectors:
                content = article_soup.select_one(selector)
                if content:
                    break
            
            if content:
                # Extract text
                article_text = content.get_text(separator='\n', strip=True)
                
                # Remove excessive whitespace
                article_text = re.sub(r'\n\s*\n', '\n\n', article_text)
                
                # Save as JSON for processing
                article_data = {
                    'title': title,
                    'url': article_url,
                    'source': 'Penn State Extension',
                    'text': article_text,
                    'type': 'university_extension'
                }
                
                filename = clean_title + '.json'
                filepath = os.path.join(TEXT_FOLDER, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(article_data, f, indent=2)
                
                print(f"  ✓ Saved article text: {filename}")
                articles_saved += 1
            else:
                print(f"  ✗ Could not extract content")
                failed.append(article_url)
        
        # Be nice to the server
        time.sleep(1)
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        failed.append(article_url)

# Summary
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}\n")
print(f"Total articles checked: {len(article_links)}")
print(f"PDFs downloaded: {pdfs_downloaded}")
print(f"Articles saved (text): {articles_saved}")
print(f"Failed: {len(failed)}")

if failed:
    print(f"\nFailed URLs:")
    for url in failed:
        print(f"  - {url}")

print(f"\n✅ PDFs saved to: {DOWNLOAD_FOLDER}")
print(f"✅ Article text saved to: {TEXT_FOLDER}")
print(f"\nNext step: Process with improved_pdf_processor.py (for PDFs)")
print(f"           Create article processor for JSON files")