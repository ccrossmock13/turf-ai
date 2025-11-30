import requests

url = "https://ordspub.epa.gov/ords/pesticides/cswu/ProductSearch/partialprodsearch/riname/Drive XLR8"
response = requests.get(url, timeout=10)

if response.status_code == 200:
    data = response.json()
    if 'items' in data:
        active = [item for item in data['items'] if item.get('product_status') == 'Active']
        for item in active:
            print(f"{item.get('productname')}")
            print(f"EPA Reg: {item.get('eparegno')}\n")
