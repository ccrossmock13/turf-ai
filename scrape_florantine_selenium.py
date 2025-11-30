from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import json

# Set up Chrome options
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

print("Setting up browser...\n")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# Create output directory
if not os.path.exists('floratine_products'):
    os.makedirs('floratine_products')

# Parse the existing scraped data to structure it better
print("Parsing and structuring Floratine products...\n")

# Read the existing file
with open('floratine_products/all_products.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# Split by category
categories = content.split('=' * 60)

products_structured = []

# Process each category
for section in categories:
    if 'FLORATINE FOLIAR PRODUCTS' in section:
        category = 'Foliar'
    elif 'FLORATINE SOIL PRODUCTS' in section:
        category = 'Soil'
    elif 'FLORATINE SPECIALTY PRODUCTS' in section:
        category = 'Specialty'
    else:
        continue
    
    print(f"Processing {category} products...")
    
    # Split into individual products (products start with all caps name)
    lines = section.split('\n')
    current_product = None
    product_data = {}
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Skip empty lines and headers
        if not line or 'Products' in line or '=' in line:
            continue
        
        # Detect product name (typically all caps or specific patterns)
        if line.isupper() and len(line) > 3 and line not in ['PACKAGING', 'RATE', 'WEIGHT', 'BENEFITS INCLUDE:']:
            # Save previous product
            if current_product and product_data:
                products_structured.append({
                    'name': current_product,
                    'category': category,
                    'data': product_data
                })
            
            # Start new product
            current_product = line
            product_data = {'description': '', 'benefits': [], 'packaging': '', 'rate': '', 'weight': ''}
            
        elif current_product:
            # Collect product details
            if 'PACKAGING' == line:
                # Next lines are packaging info
                j = i + 1
                pkg_lines = []
                while j < len(lines) and lines[j].strip() and 'RATE' not in lines[j]:
                    pkg_lines.append(lines[j].strip())
                    j += 1
                product_data['packaging'] = '\n'.join(pkg_lines)
                
            elif 'RATE' == line:
                # Next lines are rate info
                j = i + 1
                rate_lines = []
                while j < len(lines) and lines[j].strip() and 'WEIGHT' not in lines[j] and not lines[j].strip().isupper():
                    rate_lines.append(lines[j].strip())
                    j += 1
                product_data['rate'] = '\n'.join(rate_lines)
                
            elif 'WEIGHT' == line:
                # Next line is weight
                if i + 1 < len(lines):
                    product_data['weight'] = lines[i + 1].strip()
                    
            elif 'BENEFITS INCLUDE:' in line:
                # Next lines are benefits
                j = i + 1
                while j < len(lines) and lines[j].strip() and not lines[j].strip().isupper():
                    if lines[j].strip():
                        product_data['benefits'].append(lines[j].strip())
                    j += 1
                    
            elif not any(x in line for x in ['PACKAGING', 'RATE', 'WEIGHT', 'VIEW', 'CONTACT', 'LOGIN', 'COPYRIGHT']):
                # This is likely description text
                if not line.isupper() and len(line) > 20:
                    product_data['description'] += line + ' '
    
    # Save last product
    if current_product and product_data:
        products_structured.append({
            'name': current_product,
            'category': category,
            'data': product_data
        })

# Save structured JSON for reference
with open('floratine_products/products_structured.json', 'w', encoding='utf-8') as f:
    json.dump(products_structured, f, indent=2)

print(f"\n✓ Structured {len(products_structured)} products")

# Now create properly formatted text chunks for each product
print("\nCreating optimized product descriptions...\n")

formatted_products = []

for product in products_structured:
    name = product['name']
    category = product['category']
    data = product['data']
    
    # Build a comprehensive product description
    product_text = f"""PRODUCT: {name}
CATEGORY: {category}

{data['description'].strip()}

"""
    
    if data['benefits']:
        product_text += "BENEFITS:\n"
        for benefit in data['benefits']:
            product_text += f"• {benefit}\n"
        product_text += "\n"
    
    if data['rate']:
        product_text += f"APPLICATION RATE:\n{data['rate']}\n\n"
    
    if data['packaging']:
        product_text += f"PACKAGING:\n{data['packaging']}\n\n"
    
    if data['weight']:
        product_text += f"WEIGHT: {data['weight']}\n\n"
    
    # Add product to list
    formatted_products.append({
        'name': name,
        'category': category,
        'text': product_text.strip()
    })

# Save formatted products
with open('floratine_products/products_formatted.txt', 'w', encoding='utf-8') as f:
    for product in formatted_products:
        f.write('=' * 80 + '\n')
        f.write(product['text'])
        f.write('\n' + '=' * 80 + '\n\n')

print(f"✓ Created {len(formatted_products)} formatted product descriptions")
print(f"✓ Saved to floratine_products/products_formatted.txt")
print(f"✓ Saved structured data to floratine_products/products_structured.json")

# Also save individual product files for easier debugging
os.makedirs('floratine_products/individual', exist_ok=True)
for product in formatted_products:
    safe_name = product['name'].replace('/', '-').replace(' ', '_')[:50]
    with open(f'floratine_products/individual/{safe_name}.txt', 'w', encoding='utf-8') as f:
        f.write(product['text'])

print(f"✓ Saved {len(formatted_products)} individual product files")

driver.quit()
print("\n✅ Done! Ready for embedding.")
