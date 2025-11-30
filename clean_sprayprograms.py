import os
import re

# Folder to clean
FOLDER = os.path.expanduser("~/Desktop/turf-ai/static/spray-programs")

print("="*80)
print("SPRAY PROGRAM FILENAME CLEANUP")
print("="*80)
print(f"\nFolder: {FOLDER}\n")

# Get all files
files = [f for f in os.listdir(FOLDER) if f.endswith('.pdf')]

print(f"Found {len(files)} PDF files\n")

renamed = 0
skipped = 0

for filename in sorted(files):
    old_path = os.path.join(FOLDER, filename)
    
    # Clean the filename
    new_name = filename
    
    # Remove common prefixes
    new_name = re.sub(r'^(basf|syngenta|envu|bayer|corteva|quali-pro|csi)\s*[-_]?\s*', '', new_name, flags=re.IGNORECASE)
    
    # Convert underscores and multiple spaces to single space
    new_name = new_name.replace('_', ' ')
    new_name = re.sub(r'\s+', ' ', new_name)
    
    # Capitalize properly
    new_name = new_name.title()
    
    # Fix common acronyms
    new_name = re.sub(r'\bPgr\b', 'PGR', new_name)
    new_name = re.sub(r'\bNtep\b', 'NTEP', new_name)
    new_name = re.sub(r'\bUsga\b', 'USGA', new_name)
    new_name = re.sub(r'\bBmp\b', 'BMP', new_name)
    
    # Clean up spacing around hyphens
    new_name = re.sub(r'\s*-\s*', ' - ', new_name)
    
    # Remove extra extensions
    new_name = re.sub(r'\.pdf\.pdf$', '.pdf', new_name, flags=re.IGNORECASE)
    
    # Trim whitespace
    new_name = new_name.strip()
    
    new_path = os.path.join(FOLDER, new_name)
    
    if old_path != new_path:
        # Check if new name already exists
        if os.path.exists(new_path):
            print(f"⚠️  SKIP: {filename}")
            print(f"   → {new_name} already exists\n")
            skipped += 1
        else:
            os.rename(old_path, new_path)
            print(f"✓ {filename}")
            print(f"  → {new_name}\n")
            renamed += 1
    else:
        skipped += 1

print("="*80)
print("SUMMARY")
print("="*80)
print(f"Total files: {len(files)}")
print(f"Renamed: {renamed}")
print(f"Skipped: {skipped}")
print("\n✅ Cleanup complete!")