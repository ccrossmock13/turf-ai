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

print("USGA GREEN SECTION RECORD SCRAPER\n")
print("Scraping articles from USGA's premier turf publication\n")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# USGA pages to scrape
USGA_PAGES = [
    "https://www.usga.org/course-care/green-section-record.html",
    "https://www.usga.org/course-care/digital-collections.html",
]

def scrape_usga_article_page(url):
    """Scrape a USGA article listing page"""
    try:
        print(f"\nChecking: {url}")
        driver.get(url)
        time.sleep(5)
        
        # Find all article links
        article_links = []
        links = driver.find_elements(By.TAG_NAME, 'a')
        
        for link in links:
            href = link.get_attribute('href')
            if href and ('green-section-record' in href or 'digitalcollections' in href or 'course-care' in href):
                if href.endswith('.html') and href not in article_links:
                    article_links.append(href)
        
        print(f"  Found {len(article_links)} article links")
        return article_links
        
    except Exception as e:
        print(f"  Error: {e}")
        return []

def scrape_usga_article(url):
    """Scrape content from a single USGA article"""
    try:
        driver.get(url)
        time.sleep(3)
        
        # Get title
        try:
            title = driver.find_element(By.TAG_NAME, 'h1').text
        except:
            title = url.split('/')[-1].replace('.html', '').replace('-', ' ').title()
        
        # Get article content
        try:
            # Try to find main content area
            article_body = driver.find_element(By.CSS_SELECTOR, 'article, .article-body, .content, main')
            content = article_body.text
        except:
            # Fallback to body
            content = driver.find_element(By.TAG_NAME, 'body').text
        
        # Clean up content - remove navigation etc
        if len(content) > 500:
            return {
                'title': title,
                'content': content,
                'url': url
            }
        return None
        
    except Exception as e:
        return None

# Phase 1: Find all article URLs
print("="*70)
print("PHASE 1: Finding USGA Articles")
print("="*70 + "\n")

all_article_urls = []
for page in USGA_PAGES:
    articles = scrape_usga_article_page(page)
    all_article_urls.extend(articles)
    time.sleep(2)

# Remove duplicates
all_article_urls = list(set(all_article_urls))[:100]  # Limit to 100 articles

print(f"\n{'='*70}")
print(f"Found {len(all_article_urls)} unique articles to scrape")
print(f"{'='*70}\n")

# Phase 2: Scrape and upload articles
print("="*70)
print("PHASE 2: Scraping and Uploading Articles")
print("="*70 + "\n")

uploaded = 0
for i, url in enumerate(all_article_urls, 1):
    try:
        print(f"\n[{i}/{len(all_article_urls)}] Scraping article...")
        
        article = scrape_usga_article(url)
        
        if not article:
            print(f"  ⚠️  Could not extract content")
            continue
        
        print(f"  Title: {article['title'][:60]}...")
        
        # Build document text
        doc_text = f"Title: {article['title']}\n"
        doc_text += f"Source: USGA Green Section Record\n"
        doc_text += f"URL: {article['url']}\n\n"
        doc_text += article['content']
        
        # Smart chunking for large articles
        if len(doc_text) > 7000:
            chunks = [doc_text[i:i+6000] for i in range(0, len(doc_text), 6000)]
            
            for j, chunk in enumerate(chunks, start=1):
                chunk_text = f"Title: {article['title']} (Part {j}/{len(chunks)})\nSource: USGA\n\n{chunk}"
                
                response = openai_client.embeddings.create(
                    input=chunk_text,
                    model="text-embedding-3-small"
                )
                embedding = response.data[0].embedding
                
                safe_name = re.sub(r'[^a-z0-9]+', '-', article['title'].lower()).strip('-')[:100]
                
                index.upsert(vectors=[{
                    "id": f"usga-{safe_name}-{j}",
                    "values": embedding,
                    "metadata": {
                        "text": chunk_text,
                        "source": f"USGA - {article['title'][:100]}",
                        "type": "usga_article",
                        "institution": "USGA Green Section",
                        "document_name": article['title']
                    }
                }])
                
                uploaded += 1
            
            print(f"  ✓ Uploaded {len(chunks)} chunks")
        else:
            # Single chunk
            response = openai_client.embeddings.create(
                input=doc_text,
                model="text-embedding-3-small"
            )
            embedding = response.data[0].embedding
            
            safe_name = re.sub(r'[^a-z0-9]+', '-', article['title'].lower()).strip('-')[:100]
            
            index.upsert(vectors=[{
                "id": f"usga-{safe_name}",
                "values": embedding,
                "metadata": {
                    "text": doc_text,
                    "source": f"USGA - {article['title'][:100]}",
                    "type": "usga_article",
                    "institution": "USGA Green Section",
                    "document_name": article['title']
                }
            }])
            
            uploaded += 1
            print(f"  ✓ Uploaded")
        
        # Restart browser every 20 articles
        if i % 20 == 0:
            print("\n  Restarting browser...")
            driver.quit()
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            time.sleep(2)
        
    except Exception as e:
        print(f"  Error: {e}")

driver.quit()

print(f"\n{'='*70}")
print(f"✅ Complete!")
print(f"{'='*70}")
print(f"Articles scraped: {len(all_article_urls)}")
print(f"Chunks uploaded: {uploaded}")
print(f"\nYour Turf AI now has USGA Green Section content!")