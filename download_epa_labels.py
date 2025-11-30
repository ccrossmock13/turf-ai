import requests
import os
from dotenv import load_dotenv
import time

load_dotenv()

# Common turf products
products = [
    "Heritage",
    "Daconil",
    "Banner MAXX",
    "Headway",
    "Spectro",
    "Tartan",
    "Trinity",
    "Tourney",
    "Pillar",
    "Compass",
    "Segway",
    "Xzemplar",
    "Medallion",
    "Disarm",
    "Emerald",
    "Chipco",
    "Insignia",
    "Primo MAXX",
    "Trimmit",
    "Cutless",
    "Proxy",
    "Roundup",
    "Certainty",
    "Tenacity",
    "Dismiss",
    "Sedgehammer",
    "Image",
    "Drive",
    "Banol",
    "Subdue MAXX"
]

print(f"\n{'='*60}")
print(f"EPA PESTICIDE LABEL DOWNLOADER")
print(f"{'='*60}")
print(f"Searching for {len(products)} turf products\n")

# Create labels folder
if not os.path.exists('epa_labels'):
    os.makedirs('epa_labels')

found_products = []
not_found = []

for idx, product in enumerate(products, 1):
    print(f"[{idx}/{len(products)}] Searching for: {product}")
    
    try:
        # Search EPA API
        search_url = f"https://ordspub.epa.gov/ords/pesticides/cswu/ProductSearch/partialprodsearch/riname/{product}"
        
        response = requests.get(search_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if we got results
            if 'items' in data and len(data['items']) > 0:
                # Find ACTIVE products only
                active_products = [item for item in data['items'] if item.get('product_status') == 'Active']
                
                if active_products:
                    # Get first active product
                    item = active_products[0]
                    
                    product_name = item.get('productname', 'Unknown')
                    epa_reg = item.get('eparegno', 'N/A')
                    
                    print(f"  ✓ Found: {product_name}")
                    print(f"    EPA Reg: {epa_reg}")
                    print(f"    Status: Active")
                    
                    # Save label info as text
                    filename = f"epa_labels/{product.replace(' ', '_').replace('/', '-')}_{epa_reg.replace('/', '-')}.txt"
                    with open(filename, 'w') as f:
                        f.write(f"PRODUCT: {product_name}\n")
                        f.write(f"EPA REGISTRATION: {epa_reg}\n")
                        f.write(f"STATUS: {item.get('product_status', 'N/A')}\n")
                        f.write(f"STATUS DATE: {item.get('product_status_date', 'N/A')}\n")
                        if item.get('altrntbrndnames'):
                            f.write(f"ALTERNATE NAMES: {item.get('altrntbrndnames')}\n")
                        f.write(f"\nLABEL LINK: https://ordspub.epa.gov/ords/pesticides/f?p=PPLS:102:::NO::P102_REG_NUM:{epa_reg}\n")
                        f.write(f"\nNote: This is EPA registration data. For full label details,\n")
                        f.write(f"visit the label link above or use CDMS/Greenbook.\n")
                    
                    found_products.append((product, product_name, epa_reg))
                    print(f"  ✓ Saved to {filename}")
                else:
                    print(f"  ⚠ Found {len(data['items'])} results but all inactive")
                    not_found.append(product)
            else:
                print(f"  ✗ Not found in EPA database")
                not_found.append(product)
        else:
            print(f"  ✗ API error: {response.status_code}")
            not_found.append(product)
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        not_found.append(product)
    
    time.sleep(0.5)  # Be nice to EPA servers

print(f"\n{'='*60}")
print(f"SEARCH COMPLETE")
print(f"{'='*60}")
print(f"Products found: {len(found_products)}/{len(products)}")

if found_products:
    print(f"\nSuccessfully retrieved:")
    for orig, full_name, epa in found_products:
        print(f"  ✓ {orig} → {full_name} ({epa})")

if not_found:
    print(f"\nNot found or inactive ({len(not_found)}):")
    for prod in not_found[:10]:
        print(f"  - {prod}")
    if len(not_found) > 10:
        print(f"  ... and {len(not_found)-10} more")

print(f"\nLabel files saved in: epa_labels/ folder")
print(f"Next: Upload these labels to your AI database")
print(f"{'='*60}\n")
