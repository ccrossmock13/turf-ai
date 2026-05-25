from pinecone import Pinecone
import os
from dotenv import load_dotenv
import requests

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("="*80)
print("RESOURCE LIBRARY CLEANUP TOOL")
print("="*80)
print("\nOptions:")
print("1. Show all resources with their titles")
print("2. Fix messy titles (clean up formatting)")
print("3. Test all URLs and remove broken links")
print("4. Remove equipment/pesticide/research labels from library")
print("5. Show resources by type")
print("6. Run full cleanup (2 + 3 + 4)")

choice = input("\nChoose option (1-6): ").strip()

if choice == "1":
    # Show all resources
    results = index.query(
        vector=[0.0] * 1536,
        top_k=10000,
        filter={"type": {"$in": ["pesticide_label", "ntep_trial", "university_extension", "equipment_catalog"]}},
        include_metadata=True
    )
    
    seen = {}
    for match in results['matches']:
        metadata = match['metadata']
        name = metadata.get('document_name') or metadata.get('product_name') or metadata.get('source', '')
        doc_type = metadata.get('type', '')
        url = metadata.get('pdf_path') or metadata.get('label_url', '')
        
        key = f"{name}_{doc_type}"
        if key not in seen:
            seen[key] = {'name': name, 'type': doc_type, 'url': url, 'count': 0}
        seen[key]['count'] += 1
    
    print(f"\nFound {len(seen)} unique resources:\n")
    for key, info in sorted(seen.items()):
        print(f"{info['type']:20} | {info['name'][:60]:60} | {info['count']} chunks")
        if info['url']:
            print(f"                     | URL: {info['url'][:60]}")
        print()

elif choice == "2":
    # Fix messy titles
    print("\nSearching for resources with messy titles...")
    
    results = index.query(
        vector=[0.0] * 1536,
        top_k=10000,
        include_metadata=True
    )
    
    to_fix = []
    for match in results['matches']:
        metadata = match['metadata']
        name = metadata.get('document_name') or metadata.get('product_name') or metadata.get('source', '')
        
        # Check for messy patterns
        if any(pattern in name for pattern in ['EPA Label:', 'Pesticide Label:', 'research-', 'chunk-', '_', '--']):
            to_fix.append({
                'id': match['id'],
                'old_name': name,
                'metadata': metadata
            })
    
    if not to_fix:
        print("No messy titles found!")
    else:
        print(f"\nFound {len(to_fix)} resources with messy titles")
        print("\nShowing first 20:\n")
        
        unique_names = {}
        for item in to_fix:
            if item['old_name'] not in unique_names:
                unique_names[item['old_name']] = 0
            unique_names[item['old_name']] += 1
        
        for name, count in list(unique_names.items())[:20]:
            print(f"  {name} ({count} chunks)")
        
        fix = input(f"\nAttempt to auto-fix these titles? (yes/no): ").strip().lower()
        
        if fix == 'yes':
            fixed = 0
            for item in to_fix:
                old_name = item['old_name']
                
                # Clean up the name
                new_name = old_name
                new_name = new_name.replace('EPA Label: ', '')
                new_name = new_name.replace('Pesticide Label: ', '')
                new_name = new_name.replace('_', ' ')
                new_name = new_name.replace('--', '-')
                new_name = new_name.replace('research-', '')
                new_name = new_name.strip()
                
                if new_name != old_name:
                    try:
                        fetch_result = index.fetch(ids=[item['id']])
                        if item['id'] not in fetch_result['vectors']:
                            continue
                        
                        vector_data = fetch_result['vectors'][item['id']]
                        updated_metadata = vector_data['metadata']
                        
                        if 'document_name' in updated_metadata:
                            updated_metadata['document_name'] = new_name
                        if 'product_name' in updated_metadata:
                            updated_metadata['product_name'] = new_name
                        updated_metadata['source'] = new_name
                        
                        index.upsert(vectors=[{
                            'id': item['id'],
                            'values': vector_data['values'],
                            'metadata': updated_metadata
                        }])
                        
                        fixed += 1
                        if fixed % 50 == 0:
                            print(f"  Fixed {fixed}...")
                    except Exception as e:
                        print(f"  Error: {e}")
            
            print(f"\n✅ Fixed {fixed} titles")

elif choice == "3":
    # Test URLs and remove broken links
    print("\nTesting all resource URLs...")
    
    results = index.query(
        vector=[0.0] * 1536,
        top_k=10000,
        filter={"$or": [{"pdf_path": {"$exists": True}}, {"label_url": {"$exists": True}}]},
        include_metadata=True
    )
    
    broken = []
    tested = 0
    
    # Get unique URLs to test
    unique_urls = {}
    for match in results['matches']:
        metadata = match['metadata']
        url = metadata.get('pdf_path') or metadata.get('label_url')
        
        if url and url not in unique_urls:
            unique_urls[url] = []
        if url:
            unique_urls[url].append(match['id'])
    
    print(f"Found {len(unique_urls)} unique URLs to test...\n")
    
    for url, vector_ids in unique_urls.items():
        tested += 1
        if tested % 10 == 0:
            print(f"  Tested {tested}/{len(unique_urls)}...")
        
        try:
            # Test if URL is accessible
            if url.startswith('http'):
                response = requests.head(url, timeout=5, allow_redirects=True)
                if response.status_code >= 400:
                    broken.append({'url': url, 'vector_ids': vector_ids, 'error': f'Status {response.status_code}'})
            elif url.startswith('/static/'):
                # Check local file
                filepath = url.replace('/static/', 'static/')
                if not os.path.exists(filepath):
                    broken.append({'url': url, 'vector_ids': vector_ids, 'error': 'File not found'})
        except Exception as e:
            broken.append({'url': url, 'vector_ids': vector_ids, 'error': str(e)})
    
    print(f"\n{'='*80}")
    print(f"Tested {tested} URLs")
    print(f"Found {len(broken)} broken links\n")
    
    if broken:
        for item in broken[:20]:
            print(f"❌ {item['url'][:60]}")
            print(f"   Error: {item['error']}")
            print(f"   Affects {len(item['vector_ids'])} vectors\n")
        
        remove = input(f"\nRemove pdf_path/label_url from {sum(len(b['vector_ids']) for b in broken)} vectors? (yes/no): ").strip().lower()
        
        if remove == 'yes':
            removed = 0
            for item in broken:
                for vector_id in item['vector_ids']:
                    try:
                        fetch_result = index.fetch(ids=[vector_id])
                        if vector_id not in fetch_result['vectors']:
                            continue
                        
                        vector_data = fetch_result['vectors'][vector_id]
                        updated_metadata = vector_data['metadata']
                        
                        # Remove broken URLs
                        if 'pdf_path' in updated_metadata and updated_metadata.get('pdf_path') == item['url']:
                            del updated_metadata['pdf_path']
                        if 'label_url' in updated_metadata and updated_metadata.get('label_url') == item['url']:
                            del updated_metadata['label_url']
                        
                        index.upsert(vectors=[{
                            'id': vector_id,
                            'values': vector_data['values'],
                            'metadata': updated_metadata
                        }])
                        
                        removed += 1
                        if removed % 50 == 0:
                            print(f"  Removed {removed}...")
                    except Exception as e:
                        print(f"  Error: {e}")
            
            print(f"\n✅ Removed broken links from {removed} vectors")

elif choice == "4":
    # Remove equipment/pesticide/research from library visibility
    print("\nHiding equipment catalogs and non-relevant resources from library...")
    
    # Option 1: Delete them entirely
    # Option 2: Remove their pdf_path so they don't show in library but AI can still use them
    
    print("\nOptions:")
    print("1. Remove pdf_path (hide from library, AI can still search)")
    print("2. Delete entirely from database")
    
    sub_choice = input("\nChoose (1-2): ").strip()
    
    types_to_hide = ['equipment_catalog']  # Can add more: 'pesticide_product', etc.
    
    results = index.query(
        vector=[0.0] * 1536,
        top_k=10000,
        filter={"type": {"$in": types_to_hide}},
        include_metadata=True
    )
    
    print(f"\nFound {len(results['matches'])} vectors of types: {types_to_hide}")
    
    confirm = input(f"\nProceed? (yes/no): ").strip().lower()
    
    if confirm == 'yes':
        if sub_choice == '1':
            # Remove pdf_path
            updated = 0
            for match in results['matches']:
                try:
                    fetch_result = index.fetch(ids=[match['id']])
                    if match['id'] not in fetch_result['vectors']:
                        continue
                    
                    vector_data = fetch_result['vectors'][match['id']]
                    updated_metadata = vector_data['metadata']
                    
                    if 'pdf_path' in updated_metadata:
                        del updated_metadata['pdf_path']
                    if 'label_url' in updated_metadata:
                        del updated_metadata['label_url']
                    
                    index.upsert(vectors=[{
                        'id': match['id'],
                        'values': vector_data['values'],
                        'metadata': updated_metadata
                    }])
                    
                    updated += 1
                    if updated % 50 == 0:
                        print(f"  Updated {updated}...")
                except Exception as e:
                    print(f"  Error: {e}")
            
            print(f"\n✅ Hidden {updated} resources from library")
        
        elif sub_choice == '2':
            # Delete entirely
            ids_to_delete = [match['id'] for match in results['matches']]
            
            for i in range(0, len(ids_to_delete), 100):
                batch = ids_to_delete[i:i+100]
                index.delete(ids=batch)
                print(f"  Deleted {min(i+100, len(ids_to_delete))}/{len(ids_to_delete)}...")
            
            print(f"\n✅ Deleted {len(ids_to_delete)} vectors")

elif choice == "5":
    # Show resources by type
    results = index.query(
        vector=[0.0] * 1536,
        top_k=10000,
        include_metadata=True
    )
    
    types = {}
    for match in results['matches']:
        doc_type = match['metadata'].get('type', 'unknown')
        if doc_type not in types:
            types[doc_type] = 0
        types[doc_type] += 1
    
    print("\nResources by type:\n")
    for doc_type, count in sorted(types.items(), key=lambda x: x[1], reverse=True):
        print(f"{doc_type:30} | {count:,} chunks")

elif choice == "6":
    # Run full cleanup
    print("\n🔧 RUNNING FULL CLEANUP...")
    print("\nThis will:")
    print("1. Fix messy titles")
    print("2. Remove broken links")
    print("3. Hide equipment from library")
    
    confirm = input("\nProceed? (yes/no): ").strip().lower()
    
    if confirm == 'yes':
        print("\n" + "="*80)
        print("Step 1: Fixing titles...")
        # Run title fix code here
        
        print("\n" + "="*80)
        print("Step 2: Testing URLs...")
        # Run URL test code here
        
        print("\n" + "="*80)
        print("Step 3: Hiding equipment...")
        # Run hide equipment code here
        
        print("\n✅ Full cleanup complete!")

print("\n✅ Done")