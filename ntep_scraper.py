import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
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

print("NTEP TRIAL DATA SCRAPER\n")
print("Scraping cultivar trial data from ntep.org\n")

# Setup Selenium
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=chrome_options)

# NTEP trial report URLs by grass type
NTEP_URLS = {
    "Bentgrass": "https://www.ntep.org/reports/bg/",
    "Bermudagrass": "https://www.ntep.org/reports/bd/",
    "Kentucky Bluegrass": "https://www.ntep.org/reports/kb/",
    "Tall Fescue": "https://www.ntep.org/reports/tf/",
    "Perennial Ryegrass": "https://www.ntep.org/reports/pr/",
    "Fine Fescue": "https://www.ntep.org/reports/ff/",
}

def extract_pdf_text(pdf_url):
    """Download and extract text from PDF"""
    try:
        response = requests.get(pdf_url, timeout=30)
        pdf_file = BytesIO(response.content)
        
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        
        return text
    except Exception as e:
        print(f"    Error extracting PDF: {e}")
        return ""

uploaded = 0
total_chunks = 0

for grass_type, base_url in NTEP_URLS.items():
    print(f"\n{'='*70}")
    print(f"SCRAPING {grass_type.upper()} TRIALS")
    print(f"{'='*70}\n")
    
    try:
        driver.get(base_url)
        time.sleep(3)
        
        # Find all PDF links on the page
        links = driver.find_elements(By.TAG_NAME, "a")
        pdf_links = []
        
        for link in links:
            href = link.get_attribute("href")
            if href and ".pdf" in href.lower():
                # Get full URL
                if not href.startswith("http"):
                    href = base_url + href
                
                # Get link text for description
                text = link.text.strip()
                
                # Filter for final reports and recent years
                if any(keyword in text.lower() for keyword in ["final", "report", "2020", "2021", "2022", "2023", "2024"]):
                    pdf_links.append((href, text))
        
        print(f"Found {len(pdf_links)} relevant PDF reports\n")
        
        # Limit to most recent 5 reports per grass type
        pdf_links = pdf_links[:5]
        
        for i, (pdf_url, description) in enumerate(pdf_links, 1):
            try:
                print(f"[{i}/{len(pdf_links)}] {description}")
                print(f"  URL: {pdf_url}")
                print(f"  Extracting PDF...")
                
                pdf_text = extract_pdf_text(pdf_url)
                
                if not pdf_text or len(pdf_text) < 500:
                    print(f"  ⚠️  Extraction failed or empty")
                    continue
                
                print(f"  Extracted {len(pdf_text)} characters")
                
                # Build document text
                doc_text = f"NTEP Trial Report: {grass_type}\n"
                doc_text += f"Report: {description}\n"
                doc_text += f"Source: {pdf_url}\n\n"
                doc_text += pdf_text
                
                # Chunk into smaller pieces for NTEP data (4000 chars each)
                chunks = []
                current_chunk = ""
                
                lines = doc_text.split('\n')
                for line in lines:
                    current_chunk += line + '\n'
                    
                    if len(current_chunk) > 4000:
                        chunks.append(current_chunk)
                        current_chunk = ""
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                print(f"  Creating {len(chunks)} chunks...")
                
                # Upload each chunk
                for j, chunk in enumerate(chunks, start=1):
                    chunk_text = f"NTEP Trial: {grass_type} - {description} (Part {j}/{len(chunks)})\n\n{chunk[:4500]}"
                    
                    response = openai_client.embeddings.create(
                        input=chunk_text,
                        model="text-embedding-3-small"
                    )
                    embedding = response.data[0].embedding
                    
                    # Create safe ID
                    safe_desc = re.sub(r'[^a-z0-9]+', '-', description.lower()).strip('-')[:50]
                    safe_type = re.sub(r'[^a-z0-9]+', '-', grass_type.lower()).strip('-')
                    
                    index.upsert(vectors=[{
                        "id": f"ntep-{safe_type}-{safe_desc}-{j}",
                        "values": embedding,
                        "metadata": {
                            "text": chunk_text,
                            "source": f"NTEP {grass_type} - {description}",
                            "type": "ntep_trial",
                            "brand": f"NTEP {grass_type}",
                            "grass_type": grass_type,
                            "document_name": description,
                            "url": pdf_url
                        }
                    }])
                    
                    uploaded += 1
                    total_chunks += 1
                
                print(f"  ✓ Uploaded {len(chunks)} chunks")
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                print(f"  Error: {e}")
        
        # Restart browser every grass type to prevent crashes
        driver.quit()
        driver = webdriver.Chrome(options=chrome_options)
        
    except Exception as e:
        print(f"Error scraping {grass_type}: {e}")

driver.quit()

print(f"\n{'='*70}")
print(f"✅ NTEP SCRAPING COMPLETE!")
print(f"{'='*70}")
print(f"Grass types scraped: {len(NTEP_URLS)}")
print(f"Total chunks uploaded: {total_chunks}")
print(f"\nYour Turf AI now has comprehensive NTEP trial data!")
print(f"\nTry asking:")
print(f"- 'What are the top rated bentgrass cultivars for dollar spot?'")
print(f"- 'Best bermudagrass for wear tolerance according to NTEP?'")
print(f"- 'Compare Kentucky bluegrass cultivars for shade tolerance'")