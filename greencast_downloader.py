import requests
import os
from dotenv import load_dotenv
import openai
import PyPDF2
from io import BytesIO

load_dotenv()
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("="*80)
print("GREENCAST LABEL DOWNLOADER")
print("="*80)
print("\nThis script downloads labels and SDS from Greencast product pages.")
print("Works by using Greencast's direct URL patterns.\n")

download_folder = "static/pdfs"
os.makedirs(download_folder, exist_ok=True)

# Greencast URL patterns
LABEL_BASE = "https://assets.greencastonline.com/pdf/labels/"
SDS_BASE = "https://assets.greencastonline.com/pdf/msds/"

while True:
    product = input("\nEnter product name (or 'quit' to exit): ").strip()
    
    if product.lower() in ['quit', 'exit', 'q']:
        print("\n✅ Exiting. Goodbye!")
        break
    
    if not product:
        continue
    
    # Clean product name for URL
    # Examples: "Acelepryn" stays "Acelepryn"
    #           "Heritage Action" becomes "Heritage_Action" or "HeritageAction"
    
    print(f"\nTrying to download {product}...")
    
    # Try different URL formats
    product_formats = [
        product.replace(' ', ''),  # No spaces: HeritageAction
        product.replace(' ', '_'),  # Underscores: Heritage_Action
        product.replace(' ', '-'),  # Dashes: Heritage-Action
        product,  # Original with spaces
    ]
    
    found_files = []
    
    for fmt in product_formats:
        # Try Label
        label_url = f"{LABEL_BASE}{fmt}.pdf"
        try:
            response = requests.head(label_url, timeout=5)
            if response.status_code == 200:
                print(f"  ✅ Found label: {label_url}")
                found_files.append({
                    'url': label_url,
                    'type': 'Label',
                    'filename': f"{fmt}.pdf"
                })
                break
        except:
            pass
    
    for fmt in product_formats:
        # Try SDS
        sds_url = f"{SDS_BASE}{fmt}.pdf"
        try:
            response = requests.head(sds_url, timeout=5)
            if response.status_code == 200:
                print(f"  ✅ Found SDS: {sds_url}")
                found_files.append({
                    'url': sds_url,
                    'type': 'SDS',
                    'filename': f"{fmt}_SDS.pdf"
                })
                break
        except:
            pass
    
    if not found_files:
        print(f"  ❌ No files found for '{product}'")
        print(f"  Tried URL patterns:")
        print(f"    {LABEL_BASE}{product}.pdf")
        print(f"    {LABEL_BASE}{product.replace(' ', '_')}.pdf")
        print(f"    {LABEL_BASE}{product.replace(' ', '')}.pdf")
        continue
    
    # Process found files
    for file_info in found_files:
        print(f"\n{'='*60}")
        print(f"{file_info['type']}: {file_info['url']}")
        print('='*60)
        
        try:
            # Download
            print("  Downloading...")
            response = requests.get(file_info['url'], timeout=30)
            response.raise_for_status()
            
            # Extract text
            print("  Extracting text...")
            pdf_file = BytesIO(response.content)
            reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page_num in range(min(2, len(reader.pages))):
                text += reader.pages[page_num].extract_text()
            
            text = text[:2000]
            
            # Show preview
            print(f"  Preview: {text[:200]}...")
            
            # Get AI summary
            if len(text.strip()) > 50:
                print("  Generating summary...")
                summary_prompt = f"""Summarize this {file_info['type']} in 1-2 sentences:

{text}

Summary:"""

                summary_response = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": summary_prompt}],
                    max_tokens=100,
                    temperature=0.3
                )
                
                summary = summary_response.choices[0].message.content.strip()
                print(f"\n  SUMMARY: {summary}\n")
            
            # Ask to save
            print(f"  OPTIONS:")
            print(f"  1 = Save as is")
            print(f"  2 = Rename and save")
            print(f"  3 = Skip")
            
            choice = input("\n  Enter 1-3: ").strip()
            
            if choice == '1':
                # Save with default name
                filepath = os.path.join(download_folder, file_info['filename'])
                
                if os.path.exists(filepath):
                    print(f"  ⚠️  {file_info['filename']} already exists, skipping")
                else:
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    print(f"  ✅ Saved: {file_info['filename']}")
            
            elif choice == '2':
                # Rename
                new_name = input("  Enter new filename (without .pdf): ").strip()
                if new_name:
                    filepath = os.path.join(download_folder, new_name + '.pdf')
                    
                    if os.path.exists(filepath):
                        print(f"  ⚠️  {new_name}.pdf already exists, skipping")
                    else:
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        print(f"  ✅ Saved: {new_name}.pdf")
            
            else:
                print(f"  ⏭️  Skipped")
        
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print("\n" + "="*80)
    print("Ready for next product...")

print("\n✅ All saved files should now be processed with:")
print("   python improved_pdf_processor.py")