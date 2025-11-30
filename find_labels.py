import requests

products = [
    "Primo MAXX",
    "Daconil Action", 
    "Drive XLR8",
    "Acelepryn Xtra",
    "PoaCure"
]

print("\nFinding EPA registration numbers...\n")

for product in products:
    url = f"https://ordspub.epa.gov/ords/pesticides/cswu/ProductSearch/partialprodsearch/riname/{product}"
    response = requests.get(url, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        if 'items' in data:
            print(f"{product} - Found {len(data['items'])} results")
            active = [item for item in data['items'] if item.get('product_status') == 'Active']
            
            if active:
                for item in active[:3]:  # Show first 3 active products
                    print(f"  ✓ {item.get('productname')}")
                    print(f"    EPA Reg: {item.get('eparegno')}")
                print()
            else:
                print(f"  No active products found\n")
