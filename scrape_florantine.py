import requests
from bs4 import BeautifulSoup
import os

url = "https://floratine.com/foliar"

print("Fetching Floratine products...\n")

try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Create folder
    if not os.path.exists('floratine_products'):
        os.makedirs('floratine_products')
    
    # Get the main content area
    main_content = soup.find('main') or soup.find('article') or soup.find('body')
    
    if main_content:
        # Get all text, preserving structure
        text = main_content.get_text(separator='\n', strip=True)
        
        # Save it
        with open('floratine_products/foliar_products.txt', 'w', encoding='utf-8') as f:
            f.write("FLORATINE FOLIAR PRODUCTS\n")
            f.write("="*60 + "\n\n")
            f.write(text)
        
        print(f"✓ Saved to floratine_products/foliar_products.txt")
        print(f"  Text length: {len(text):,} characters")
        
        # Show first 500 chars as preview
        print(f"\nPreview:")
        print(text[:500])
    else:
        print("Could not find main content")
    
except Exception as e:
    print(f"✗ Error: {e}")