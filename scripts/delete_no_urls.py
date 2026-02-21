from pinecone import Pinecone
import os
from dotenv import load_dotenv
import requests

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("="*80)
print("URL VALIDATOR - TEST ALL SOURCES")
print("="*80)
print("\nThis will test every URL in the database and show you broken links.\n")

# Query all vectors with URLs
results = index.query(
    vector=[0.0] * 1536,
    top_k=10000,
    include_metadata=True
)

print("Collecting all unique URLs...")

# Get unique URLs
url_to_vectors = {}  # url -> list of vector IDs
for match in results['matches']:
    metadata = match['metadata']
    url = metadata.get('pdf_path') or metadata.get('label_url') or metadata.get('url')
    
    if url:
        if url not in url_to_vectors:
            url_to_vectors[url] = []
        url_to_vectors[url].append({
            'id': match['id'],
            'name': metadata.get('document_name') or metadata.get('product_name') or metadata.get('source', ''),
            'type': metadata.get('type', '')
        })

print(f"Found {len(url_to_vectors)} unique URLs to test\n")

# Test each URL
working = []
broken = []
tested = 0

for url, vectors in url_to_vectors.items():
    tested += 1
    
    if tested % 10 == 0:
        print(f"  Testing... {tested}/{len(url_to_vectors)}")
    
    status = "unknown"
    error = ""
    
    try:
        if url.startswith('http'):
            # External URL - test with HEAD request
            response = requests.head(url, timeout=5, allow_redirects=True)
            if response.status_code < 400:
                status = "working"
            else:
                status = "broken"
                error = f"HTTP {response.status_code}"
        
        elif url.startswith('/static/'):
            # Local file - check if exists
            filepath = url.replace('/static/', 'static/')
            if os.path.exists(filepath):
                status = "working"
            else:
                status = "broken"
                error = "File not found"
        
        else:
            status = "broken"
            error = "Invalid URL format"
    
    except Exception as e:
        status = "broken"
        error = str(e)[:50]
    
    if status == "working":
        working.append({
            'url': url,
            'vectors': vectors
        })
    else:
        broken.append({
            'url': url,
            'vectors': vectors,
            'error': error
        })

# Summary
print(f"\n{'='*80}")
print("RESULTS")
print("="*80)
print(f"\n✅ Working URLs: {len(working)}")
print(f"❌ Broken URLs: {len(broken)}")

if not broken:
    print("\n🎉 All URLs are working!")
    exit()

# Show broken URLs
print(f"\n{'='*80}")
print("BROKEN URLS")
print("="*80 + "\n")

for i, item in enumerate(broken, 1):
    print(f"{i}. {item['url']}")
    print(f"   Error: {item['error']}")
    print(f"   Affects {len(item['vectors'])} vectors:")
    
    # Show affected documents (unique names only)
    unique_names = list(set([v['name'] for v in item['vectors']]))
    for name in unique_names[:5]:
        print(f"     • {name[:60]}")
    if len(unique_names) > 5:
        print(f"     ... and {len(unique_names) - 5} more")
    print()

# Options
print("="*80)
print("OPTIONS")
print("="*80)
print("\n1. Remove broken URLs from vectors (they won't show in library/citations)")
print("2. Export broken URL list to file (so you can fix them manually)")
print("3. Exit (do nothing)")

choice = input("\nChoose (1-3): ").strip()

if choice == '1':
    # Remove broken URLs
    print(f"\nRemoving broken URLs from {sum(len(b['vectors']) for b in broken)} vectors...")
    
    removed = 0
    for item in broken:
        for vector_info in item['vectors']:
            try:
                fetch_result = index.fetch(ids=[vector_info['id']])
                if vector_info['id'] not in fetch_result['vectors']:
                    continue
                
                vector_data = fetch_result['vectors'][vector_info['id']]
                updated_metadata = vector_data['metadata']
                
                # Remove the broken URL
                if 'pdf_path' in updated_metadata and updated_metadata['pdf_path'] == item['url']:
                    del updated_metadata['pdf_path']
                if 'label_url' in updated_metadata and updated_metadata['label_url'] == item['url']:
                    del updated_metadata['label_url']
                if 'url' in updated_metadata and updated_metadata['url'] == item['url']:
                    del updated_metadata['url']
                
                index.upsert(vectors=[{
                    'id': vector_info['id'],
                    'values': vector_data['values'],
                    'metadata': updated_metadata
                }])
                
                removed += 1
                if removed % 50 == 0:
                    print(f"  Removed {removed}...")
            
            except Exception as e:
                print(f"  Error: {e}")
    
    print(f"\n✅ Removed broken URLs from {removed} vectors")

elif choice == '2':
    # Export to file
    with open('broken_urls.txt', 'w') as f:
        f.write("BROKEN URLS REPORT\n")
        f.write("="*80 + "\n\n")
        
        for item in broken:
            f.write(f"URL: {item['url']}\n")
            f.write(f"Error: {item['error']}\n")
            f.write(f"Affects {len(item['vectors'])} vectors:\n")
            
            unique_names = list(set([v['name'] for v in item['vectors']]))
            for name in unique_names:
                f.write(f"  • {name}\n")
            f.write("\n")
    
    print("\n✅ Exported to broken_urls.txt")

else:
    print("\n❌ No action taken")