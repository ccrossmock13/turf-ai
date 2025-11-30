import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import openai
from dotenv import load_dotenv
import PyPDF2
from io import BytesIO
import time

# Try to import Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️  Selenium not installed. Install with: pip install selenium --break-system-packages")
    print("Some sites (like Greencast) require Selenium to load JavaScript content.\n")

load_dotenv()
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("="*80)
print("PDF FINDER WITH JAVASCRIPT SUPPORT (CONTINUOUS MODE)")
print("="*80)
print("\nThis script will:")
print("1. Crawl websites for PDF links (including JavaScript-loaded content)")
print("2. Download and summarize each PDF")
print("3. Let you decide which to keep and what to name them")
print("4. Save approved PDFs to static/pdfs/")
print("5. Keep running - process multiple sites without restarting\n")

if SELENIUM_AVAILABLE:
    print("✅ Selenium available - can handle JavaScript sites like Greencast\n")
else:
    print("⚠️  Selenium not available - JavaScript sites may not work\n")

download_folder = "static/pdfs"
os.makedirs(download_folder, exist_ok=True)

def get_pdfs_with_selenium(url):
    """Use Selenium to find PDFs on JavaScript-heavy sites"""
    if not SELENIUM_AVAILABLE:
        return []
    
    print("  Using Selenium (JavaScript support)...")
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        
        # Dismiss any alerts/popups
        try:
            WebDriverWait(driver, 3).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert.dismiss()
            print("  Dismissed popup alert")
        except:
            pass  # No alert
        
        # Scroll to bottom to trigger lazy-loaded content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Scroll back to top
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
        # Wait for all content to load
        time.sleep(3)
        
        pdf_links = []
        
        # GREENCAST SPECIFIC: Look for "Label Downloads" section
        if 'greencast' in url.lower():
            print("  Detected Greencast - grabbing ALL PDFs on page...")
            
            # Get page source and parse with BeautifulSoup
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Find ALL links with .pdf
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text(strip=True)
                
                # Make absolute URL
                if not href.startswith('http'):
                    href = urljoin(url, href)
                
                # Grab EVERYTHING with .pdf - no filtering
                if '.pdf' in href.lower():
                    pdf_links.append({
                        'url': href,
                        'text': text if text else 'PDF Document',
                        'filename': os.path.basename(urlparse(href).path) or 'document.pdf'
                    })
        
        else:
            # Generic PDF finding for other sites
            links = driver.find_elements(By.TAG_NAME, 'a')
            
            for link in links:
                try:
                    href = link.get_attribute('href')
                    text = link.text.strip()
                    
                    if href and ('.pdf' in href.lower() or 'label' in text.lower() or 'sds' in text.lower() or 'sheet' in text.lower()):
                        pdf_links.append({
                            'url': href,
                            'text': text,
                            'filename': os.path.basename(urlparse(href).path) or 'document.pdf'
                        })
                except:
                    continue
        
        driver.quit()
        
        # Remove duplicates
        seen = set()
        unique_pdfs = []
        for pdf in pdf_links:
            if pdf['url'] not in seen:
                seen.add(pdf['url'])
                unique_pdfs.append(pdf)
        
        return unique_pdfs
    
    except Exception as e:
        print(f"  Selenium error: {e}")
        return []

def get_pdfs_with_requests(url):
    """Use requests/BeautifulSoup for simple sites"""
    print("  Using BeautifulSoup (basic scraping)...")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"  Error fetching page: {e}")
        return []
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    pdf_links = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        
        is_pdf = False
        if href.lower().endswith('.pdf'):
            is_pdf = True
        elif '.pdf' in href.lower():
            is_pdf = True
        elif any(pattern in href.lower() for pattern in ['/pdf/', '/download/', '/label/', '/documents/']):
            try:
                head_response = requests.head(urljoin(url, href), timeout=5, allow_redirects=True)
                content_type = head_response.headers.get('content-type', '').lower()
                if 'pdf' in content_type:
                    is_pdf = True
            except:
                pass
        
        if is_pdf:
            full_url = urljoin(url, href)
            link_text = link.get_text(strip=True)
            
            pdf_links.append({
                'url': full_url,
                'text': link_text,
                'filename': os.path.basename(urlparse(full_url).path) or 'document.pdf'
            })
    
    return pdf_links

while True:
    url = input("\nEnter website URL to crawl (or 'quit' to exit): ").strip()
    
    if url.lower() in ['quit', 'exit', 'q']:
        print("\n✅ Exiting. Goodbye!")
        break
    
    if not url:
        continue
        
    if not url.startswith('http'):
        url = 'https://' + url
    
    print(f"\nCrawling {url} for PDFs...")
    
    # Detect if this is a JavaScript-heavy site
    use_selenium = False
    if any(domain in url.lower() for domain in ['greencast', 'envu.com', 'syngenta']):
        use_selenium = True
        print("  Detected JavaScript site - using Selenium")
    
    # Get PDFs
    if use_selenium and SELENIUM_AVAILABLE:
        pdf_links = get_pdfs_with_selenium(url)
    else:
        pdf_links = get_pdfs_with_requests(url)
    
    if not pdf_links:
        print("❌ No PDF links found on this page")
        
        if use_selenium and not SELENIUM_AVAILABLE:
            print("💡 This site may need Selenium. Install with:")
            print("   pip install selenium --break-system-packages")
        
        continue

    print(f"\n✅ Found {len(pdf_links)} PDF links:\n")
    for i, pdf in enumerate(pdf_links, 1):
        print(f"{i}. {pdf['filename']}")
        if pdf['text']:
            print(f"   Link text: {pdf['text']}")

    print("\n" + "="*80)
    choice = input(f"\nProcess these {len(pdf_links)} PDFs? (yes/no/skip): ").strip().lower()

    if choice == 'skip':
        continue
    elif choice != 'yes':
        continue

    # Process each PDF
    approved = []

    for i, pdf in enumerate(pdf_links, 1):
        print(f"\n{'='*80}")
        print(f"PDF {i}/{len(pdf_links)}: {pdf['filename']}")
        print('='*80)
        
        try:
            print("  Downloading...")
            pdf_response = requests.get(pdf['url'], timeout=30)
            pdf_response.raise_for_status()
            
            print("  Extracting text...")
            pdf_file = BytesIO(pdf_response.content)
            reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page_num in range(min(2, len(reader.pages))):
                text += reader.pages[page_num].extract_text()
            
            text = text[:3000]
            
            if len(text.strip()) < 50:
                summary = "⚠️  Unable to extract text from PDF (may be image-based or encrypted). Check manually."
            else:
                print("  Generating summary...")
                summary_prompt = f"""Summarize this PDF in 2-3 sentences. Include:
- What type of document it is (research paper, product label, guide, etc.)
- Main topic/subject
- Who published it (if visible)

Text from PDF:
{text}

Summary:"""

                summary_response = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": summary_prompt}],
                    max_tokens=150,
                    temperature=0.3
                )
                
                summary = summary_response.choices[0].message.content.strip()
            
            print(f"\n  SUMMARY:")
            print(f"  {summary}\n")
            print(f"  Original filename: {pdf['filename']}")
            if pdf['text']:
                print(f"  Link text: {pdf['text']}")
            print(f"  URL: {pdf['url']}\n")
            
            print("  OPTIONS:")
            print("  1 = Download and keep (you'll rename it)")
            print("  2 = Skip this PDF")
            
            user_choice = input("\n  Enter 1 or 2: ").strip()
            
            if user_choice == '1':
                suggested_name = input("  Enter new filename (without .pdf): ").strip()
                
                if suggested_name:
                    approved.append({
                        'content': pdf_response.content,
                        'filename': suggested_name + '.pdf',
                        'url': pdf['url']
                    })
                    print(f"  ✅ Will save as: {suggested_name}.pdf")
                else:
                    print(f"  ⚠️  No filename entered, skipping")
            else:
                print(f"  ⏭️  Skipped")
            
        except Exception as e:
            print(f"  ❌ Error processing PDF: {e}")

    if approved:
        print(f"\n{'='*80}")
        print(f"SAVING {len(approved)} APPROVED PDFs")
        print('='*80 + "\n")

        saved = 0
        for pdf in approved:
            filepath = os.path.join(download_folder, pdf['filename'])
            
            if os.path.exists(filepath):
                print(f"⚠️  {pdf['filename']} already exists, skipping")
                continue
            
            with open(filepath, 'wb') as f:
                f.write(pdf['content'])
            
            print(f"✅ Saved: {pdf['filename']}")
            saved += 1

        print(f"\n✅ Saved {saved} PDFs to {download_folder}")
    else:
        print("\nNo PDFs approved from this site")
    
    print("\n" + "="*80)
    print("Ready for next website...")