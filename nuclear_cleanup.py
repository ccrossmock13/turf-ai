from pinecone import Pinecone
import os
from dotenv import load_dotenv
import re

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("="*80)
print("NUCLEAR CLEANUP - DELETE GARBAGE, KEEP ONLY PROFESSIONAL RESOURCES")
print("="*80)

print("\nThis will DELETE vectors with:")
print("  ❌ Garbage names (hex codes, random numbers, weird characters)")
print("  ❌ Equipment catalogs (NTEP equipment programs)")
print("  ❌ Broken links")
print("\nThis will KEEP:")
print("  ✅ Clean product labels (Syngenta, Envu, BASF)")
print("  ✅ NTEP trials (actual turf trials, not equipment)")
print("  ✅ Equipment catalogs (Toro, John Deere, irrigation, etc.)")
print("  ✅ GCM magazines")
print("  ✅ Well-named research papers")
print("  ✅ University extension articles\n")

# Query everything
print("Scanning database...")
results = index.query(
    vector=[0.0] * 1536,
    top_k=10000,
    include_metadata=True
)

print(f"Found {len(results['matches'])} total vectors\n")

# Categorize vectors
to_delete = []
to_keep = []

for match in results['matches']:
    metadata = match['metadata']
    vector_id = match['id']
    name = metadata.get('document_name') or metadata.get('product_name') or metadata.get('source', '')
    doc_type = metadata.get('type', '')
    url = metadata.get('pdf_path') or metadata.get('label_url', '')
    
    delete_this = False
    reason = ""
    
    # Check for garbage patterns
    garbage_patterns = [
        r'^[a-f0-9]{32,}',  # Long hex strings
        r'^\d{12,}',  # Long number strings (12+ digits)
        r'^[A-F0-9]{10,}',  # Uppercase hex
        r'^4\s',  # Names starting with "4 " (garbage files)
        r'⊠',  # Weird characters
        r'\[D\⊠',  # More weird characters
        r'^chunk-',  # Leftover chunk IDs
        r'^local-',  # Old local IDs
        r'EPA Label: .+_\d+-\d+',  # Old EPA format
        r'Pesticide Label: .+ Label',  # Redundant label format
    ]
    
    for pattern in garbage_patterns:
        if re.search(pattern, name):
            delete_this = True
            reason = f"Garbage name pattern: {pattern}"
            break
    
    # Delete if name contains "equipment" and it's an NTEP label/trial (not actual equipment info)
    # BUT: Keep Syngenta agronomic programs (they mention grass types and locations)
    is_syngenta_program = any(keyword in name.lower() for keyword in ['greens', 'fairway', 'tees', 'bermudagrass', 'bentgrass', 'day'])
    
    if 'equipment' in name.lower() and doc_type in ['pesticide_label', 'ntep_trial'] and not is_syngenta_program:
        delete_this = True
        reason = "Equipment label/trial (not actual equipment info)"
    
    # Delete reference_document type (old garbage)
    if doc_type == 'reference_document':
        delete_this = True
        reason = "Old reference_document type"
    
    # Delete if no URL (can't show in library anyway)
    if not url and doc_type in ['pesticide_label', 'ntep_trial', 'university_extension']:
        delete_this = True
        reason = "No URL - can't display in library"
    
    if delete_this:
        to_delete.append({
            'id': vector_id,
            'name': name,
            'type': doc_type,
            'reason': reason
        })
    else:
        to_keep.append({
            'id': vector_id,
            'name': name,
            'type': doc_type
        })

# Show summary
print("="*80)
print("DELETION SUMMARY")
print("="*80)

print(f"\n📊 WILL DELETE: {len(to_delete)} vectors")
print(f"✅ WILL KEEP: {len(to_keep)} vectors\n")

# Group deletions by reason
reasons = {}
for item in to_delete:
    if item['reason'] not in reasons:
        reasons[item['reason']] = []
    reasons[item['reason']].append(item['name'])

print("Deletion breakdown by reason:\n")
for reason, names in reasons.items():
    unique_names = list(set(names))[:5]  # Show first 5 unique
    print(f"  {reason}: {len(names)} vectors")
    for name in unique_names:
        print(f"    • {name[:70]}")
    if len(names) > 5:
        print(f"    ... and {len(names) - 5} more")
    print()

# Group keeps by type
keep_types = {}
for item in to_keep:
    if item['type'] not in keep_types:
        keep_types[item['type']] = []
    keep_types[item['type']].append(item['name'])

print("="*80)
print("WHAT WILL BE KEPT")
print("="*80 + "\n")

for doc_type, names in keep_types.items():
    unique_names = list(set(names))
    print(f"{doc_type}: {len(unique_names)} unique documents ({len(names)} total chunks)")
    for name in unique_names[:10]:
        print(f"  • {name[:70]}")
    if len(unique_names) > 10:
        print(f"  ... and {len(unique_names) - 10} more")
    print()

# Confirm deletion
print("="*80)
print("⚠️  WARNING: THIS WILL PERMANENTLY DELETE VECTORS")
print("="*80)
print(f"\nYou are about to delete {len(to_delete)} vectors from Pinecone.")
print("The AI will lose access to this content (but can be re-uploaded if needed).\n")

confirm = input("Type 'DELETE' in all caps to confirm: ").strip()

if confirm != 'DELETE':
    print("\n❌ Cancelled. No vectors deleted.")
    exit()

# Delete in batches
print(f"\n🗑️  Deleting {len(to_delete)} vectors...")

deleted = 0
ids_to_delete = [item['id'] for item in to_delete]

for i in range(0, len(ids_to_delete), 100):
    batch = ids_to_delete[i:i+100]
    index.delete(ids=batch)
    deleted += len(batch)
    print(f"  Deleted {deleted}/{len(ids_to_delete)}...")

print(f"\n{'='*80}")
print(f"✅ CLEANUP COMPLETE!")
print(f"{'='*80}")
print(f"Deleted: {deleted} vectors")
print(f"Remaining: {len(to_keep)} vectors")
print(f"\nYour Resource Library should now look professional!")
print(f"Restart Flask and check it out.")