import os
import re
import shutil

PDF_FOLDER = "static/pdfs"
RENAMED_TRACKING = "renamed_weird_pdfs.txt"

print("FINDING PDFs WITH WEIRD NAMES\n")
print("="*80)

# Load already renamed files
already_renamed = set()
if os.path.exists(RENAMED_TRACKING):
    with open(RENAMED_TRACKING, 'r') as f:
        already_renamed = set(line.strip() for line in f)

# Get all PDFs
all_pdfs = [f for f in os.listdir(PDF_FOLDER) if f.endswith('.pdf')]

def is_weird_name(filename):
    """Detect if filename is cryptic/weird"""
    name = filename.replace('.pdf', '')
    
    # Skip GCM magazines (year + month pattern like 2024jan, 2019feb)
    if re.match(r'^\d{4}(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', name.lower()):
        return False
    
    # Check for patterns of weird names
    patterns = [
        r'^[a-f0-9]{32,}',  # Long hex strings (15c11b43f066efd...)
        r'^[a-f0-9]{8}-[a-f0-9]{4}',  # UUID-like (42085ceb-730f-422a...)
        r'^\d{12,}',  # Long number strings (180828190356)
        r'^[a-zA-Z0-9]{6,8}-',  # Short codes with dashes (2QvaV6-, L6oCqb-)
        r'^\w{1,3}\d{2}[_\-]',  # Research codes (cs15l_, ff20_, bg19_)
    ]
    
    for pattern in patterns:
        if re.match(pattern, name):
            return True
    
    # Also flag very short cryptic names
    if len(name) < 4 and not name.isdigit():
        return True
    
    return False

# Find weird ones (excluding already renamed)
weird_pdfs = []
normal_pdfs = []

for pdf in all_pdfs:
    # Skip if already renamed
    if pdf in already_renamed:
        continue
        
    if is_weird_name(pdf):
        weird_pdfs.append(pdf)
    else:
        normal_pdfs.append(pdf)

print(f"Total PDFs: {len(all_pdfs)}")
print(f"Normal names: {len(normal_pdfs)}")
print(f"Already renamed: {len(already_renamed)}")
print(f"Weird names (new): {len(weird_pdfs)}\n")

if not weird_pdfs:
    print("No weird filenames found!")
    exit()

print("PDFs with weird names:")
print("="*80)
for i, pdf in enumerate(weird_pdfs, 1):
    print(f"{i}. {pdf}")

print("\n" + "="*80)
print("OPTIONS:")
print("1. Move weird PDFs to separate folder (static/pdfs/weird_names/)")
print("2. List them to a text file for manual review")
print("3. Try to rename them based on PDF content")
print("4. Just list them (no action)")

choice = input("\nEnter choice (1-4): ").strip()

if choice == "1":
    # Move to separate folder
    weird_folder = os.path.join(PDF_FOLDER, "weird_names")
    os.makedirs(weird_folder, exist_ok=True)
    
    moved = 0
    for pdf in weird_pdfs:
        try:
            src = os.path.join(PDF_FOLDER, pdf)
            dst = os.path.join(weird_folder, pdf)
            shutil.move(src, dst)
            moved += 1
        except Exception as e:
            print(f"Error moving {pdf}: {e}")
    
    print(f"\n✅ Moved {moved} PDFs to {weird_folder}")
    print("You can now manually rename them and move them back")

elif choice == "2":
    # Write to text file
    with open('weird_filenames.txt', 'w') as f:
        f.write("PDFs with weird/cryptic filenames:\n\n")
        for pdf in weird_pdfs:
            f.write(f"{pdf}\n")
    
    print("\n✅ List saved to weird_filenames.txt")

elif choice == "3":
    # Try to rename based on content with AI suggestions
    print("\nThis will read each PDF and suggest better names...")
    print("You can choose from suggestions or enter your own name.")
    confirm = input("\nContinue? (yes/no): ").strip().lower()
    
    if confirm == 'yes':
        import PyPDF2
        import openai
        from dotenv import load_dotenv
        
        load_dotenv()
        openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        renamed = 0
        for pdf in weird_pdfs:
            filepath = os.path.join(PDF_FOLDER, pdf)
            
            try:
                # Read first 2 pages
                with open(filepath, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for i in range(min(2, len(reader.pages))):
                        text += reader.pages[i].extract_text()
                
                text = text[:2000]  # Limit to 2000 chars
                
                # Ask AI for name suggestions
                prompt = f"""Based on this PDF content, suggest 3 SHORT, descriptive filenames (max 60 chars each).

REQUIRED FORMAT: source-topic-year
- Source: USGA, GCM, University name, journal, company, etc.
- Topic: What it's about (disease, maintenance, equipment, etc.)
- Year: Publication year (if visible in content)

Content:
{text}

Return ONLY 3 filenames, one per line. No explanations.

Examples:
usga-dollar-spot-control-2019
gcm-magazine-irrigation-management-2024
rutgers-bentgrass-fertility-2018
penn-state-pythium-research-2020
syngenta-heritage-label-2023"""

                response = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0.3
                )
                
                suggestions = response.choices[0].message.content.strip().split('\n')
                suggestions = [s.strip() for s in suggestions if s.strip()][:3]
                
                # Sanitize suggestions - remove invalid filename characters
                sanitized_suggestions = []
                for s in suggestions:
                    # Remove .pdf if AI added it
                    s = s.replace('.pdf', '')
                    # Remove invalid characters: / \ : * ? " < > |
                    s = re.sub(r'[/\\:*?"<>|]', '-', s)
                    # Remove extra dashes
                    s = re.sub(r'-+', '-', s)
                    # Trim to 60 chars
                    s = s[:60].strip('-')
                    sanitized_suggestions.append(s)
                
                suggestions = sanitized_suggestions
                
                # Show options
                print(f"\n{'='*80}")
                print(f"Current: {pdf}")
                print(f"{'='*80}")
                print(f"First 200 chars of content:\n{text[:200]}...\n")
                print("Suggested names:")
                for i, suggestion in enumerate(suggestions, 1):
                    print(f"  {i}. {suggestion}.pdf")
                print(f"  4. Enter custom name")
                print(f"  5. Keep current name (already good)")
                print(f"  6. Skip this file")
                
                choice = input("\nChoose option (1-6): ").strip()
                
                new_name = None
                keep_current = False
                
                if choice in ['1', '2', '3']:
                    idx = int(choice) - 1
                    if idx < len(suggestions):
                        new_name = suggestions[idx] + '.pdf'
                elif choice == '4':
                    custom = input("Enter custom filename (without .pdf): ").strip()
                    if custom:
                        new_name = custom + '.pdf'
                elif choice == '5':
                    # Keep current name, just mark as processed
                    keep_current = True
                    print(f"✅ Keeping current name: {pdf}")
                    with open(RENAMED_TRACKING, 'a') as f:
                        f.write(f"{pdf}\n")
                
                if new_name:
                    new_filepath = os.path.join(PDF_FOLDER, new_name)
                    
                    # Check if exists
                    if os.path.exists(new_filepath):
                        print(f"❌ File {new_name} already exists, skipping")
                    else:
                        os.rename(filepath, new_filepath)
                        print(f"✅ Renamed to: {new_name}")
                        renamed += 1
                        
                        # Track this rename
                        with open(RENAMED_TRACKING, 'a') as f:
                            f.write(f"{pdf}\n")
                
            except Exception as e:
                print(f"Error processing {pdf}: {e}")
        
        print(f"\n{'='*80}")
        print(f"✅ Renamed {renamed} PDFs")
        print(f"{'='*80}")

elif choice == "4":
    print("\nNo action taken. List shown above.")

print("\nDone!")