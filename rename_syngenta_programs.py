from pinecone import Pinecone
import os
from dotenv import load_dotenv
import re

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("="*80)
print("SYNGENTA PROGRAM RENAMER")
print("="*80)
print("\nThis will rename Syngenta agronomic programs to professional format:\n")
print("BEFORE: 202 6 Greens – Ovs Bermudagrass – Deserts, Ca, Az, Nv, Ut")
print("AFTER:  Syngenta Greens Program - Bermudagrass - Desert Region\n")

# Query all vectors
results = index.query(
    vector=[0.0] * 1536,
    top_k=10000,
    include_metadata=True
)

# Find Syngenta programs
syngenta_programs = []

for match in results['matches']:
    metadata = match['metadata']
    name = metadata.get('document_name') or metadata.get('product_name') or metadata.get('source', '')
    
    # Pattern: starts with "20X X" and contains grass types and regions
    # Examples: "202 6 Greens", "202 6 – Fairway"
    is_syngenta = (
        re.match(r'^20\d\s+\d+', name) or  # Starts with 20X X
        ('greens' in name.lower() or 'fairway' in name.lower() or 'tees' in name.lower()) and
        ('bermudagrass' in name.lower() or 'bentgrass' in name.lower() or 'poa' in name.lower()) and
        any(region in name.lower() for region in ['desert', 'hawaii', 'midwest', 'southeast', 'transition', 'north', 'great lakes'])
    )
    
    if is_syngenta:
        syngenta_programs.append({
            'id': match['id'],
            'old_name': name,
            'metadata': metadata
        })

# Get unique program names
unique_programs = {}
for prog in syngenta_programs:
    if prog['old_name'] not in unique_programs:
        unique_programs[prog['old_name']] = 0
    unique_programs[prog['old_name']] += 1

print(f"Found {len(unique_programs)} unique Syngenta programs:\n")
for name, count in sorted(unique_programs.items()):
    print(f"  {name} ({count} chunks)")

if not syngenta_programs:
    print("\nNo Syngenta programs found!")
    exit()

print(f"\n{'='*80}")

def clean_syngenta_name(old_name):
    """Convert messy Syngenta name to professional format"""
    
    # Extract components
    name = old_name
    
    # Remove leading numbers and dashes
    name = re.sub(r'^20\d+\s*\d*\s*[-–—]\s*', '', name)
    
    # Identify turf area
    turf_area = "Program"
    if 'greens' in name.lower():
        turf_area = "Greens Program"
    elif 'fairway' in name.lower():
        turf_area = "Fairway Program"
    elif 'tees' in name.lower():
        turf_area = "Tees Program"
    
    # Identify grass type
    grass_type = ""
    if 'bentgrass' in name.lower() or 'creeping bent' in name.lower():
        grass_type = "Bentgrass"
    elif 'bermudagrass' in name.lower() or 'bermuda' in name.lower():
        grass_type = "Bermudagrass"
    elif 'poa annua' in name.lower() or 'poa' in name.lower():
        grass_type = "Poa Annua"
    elif 'ovs' in name.lower():
        grass_type = "Overseed"
    
    # Identify region
    region = ""
    if 'desert' in name.lower():
        region = "Desert Region"
    elif 'hawaii' in name.lower():
        region = "Hawaii"
    elif 'midwest' in name.lower():
        region = "Midwest"
    elif 'great lakes' in name.lower():
        region = "Great Lakes"
    elif 'southeast' in name.lower():
        region = "Southeast"
    elif 'transition' in name.lower():
        region = "Transition Zone"
    elif 'north' in name.lower():
        region = "Northern Region"
    
    # Identify day interval
    day_interval = ""
    if '14 day' in name.lower() or '14-day' in name.lower():
        day_interval = "14-Day"
    elif '7 day' in name.lower() or '7-day' in name.lower():
        day_interval = "7-Day"
    elif '21 day' in name.lower() or '21-day' in name.lower():
        day_interval = "21-Day"
    
    # Build new name
    parts = ["Syngenta", turf_area]
    
    if grass_type:
        parts.append(grass_type)
    
    if region:
        parts.append(region)
    
    if day_interval:
        parts.append(day_interval)
    
    new_name = " - ".join(parts)
    
    return new_name

# Preview renames
print("Preview of renames:\n")
preview = {}
for prog in syngenta_programs:
    old = prog['old_name']
    new = clean_syngenta_name(old)
    
    if old not in preview:
        preview[old] = new
        print(f"BEFORE: {old}")
        print(f"AFTER:  {new}\n")
        
        if len(preview) >= 10:
            break

if len(unique_programs) > 10:
    print(f"... and {len(unique_programs) - 10} more")

print(f"\n{'='*80}")
confirm = input(f"\nRename {len(syngenta_programs)} vectors? (yes/no): ").strip().lower()

if confirm != 'yes':
    print("Cancelled")
    exit()

# Rename
print(f"\nRenaming {len(syngenta_programs)} vectors...")
renamed = 0

for prog in syngenta_programs:
    new_name = clean_syngenta_name(prog['old_name'])
    
    try:
        fetch_result = index.fetch(ids=[prog['id']])
        if prog['id'] not in fetch_result['vectors']:
            continue
        
        vector_data = fetch_result['vectors'][prog['id']]
        updated_metadata = vector_data['metadata']
        
        # Update all name fields
        if 'document_name' in updated_metadata:
            updated_metadata['document_name'] = new_name
        if 'product_name' in updated_metadata:
            updated_metadata['product_name'] = new_name
        updated_metadata['source'] = new_name
        
        # Update type and brand
        updated_metadata['type'] = 'university_extension'
        updated_metadata['brand'] = 'Syngenta'
        
        index.upsert(vectors=[{
            'id': prog['id'],
            'values': vector_data['values'],
            'metadata': updated_metadata
        }])
        
        renamed += 1
        if renamed % 20 == 0:
            print(f"  Renamed {renamed}/{len(syngenta_programs)}...")
    
    except Exception as e:
        print(f"  Error: {e}")

print(f"\n{'='*80}")
print(f"✅ COMPLETE!")
print(f"{'='*80}")
print(f"Renamed {renamed} vectors")
print(f"Syngenta programs now have professional names!")