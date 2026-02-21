import PyPDF2

# Open the PDF
pdf_file = open('paper.pdf', 'rb')
pdf_reader = PyPDF2.PdfReader(pdf_file)

print(f"Number of pages: {len(pdf_reader.pages)}")
print("\n--- First page text ---\n")

# Extract text from first page
first_page = pdf_reader.pages[0]
text = first_page.extract_text()
print(text)

pdf_file.close()
