import PyPDF2
import openai
import os
from dotenv import load_dotenv

load_dotenv()

# Extract text from PDF
pdf_file = open('paper.pdf', 'rb')
pdf_reader = PyPDF2.PdfReader(pdf_file)

# Get first 5 pages (enough for intro/abstract)
text = ""
for page_num in range(min(5, len(pdf_reader.pages))):
    text += pdf_reader.pages[page_num].extract_text()

pdf_file.close()

print("Extracted text from PDF...")
print(f"Text length: {len(text)} characters\n")

# Ask AI about it
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a turfgrass science expert. Answer based only on the provided research paper excerpt."},
        {"role": "user", "content": f"Based on this research paper:\n\n{text}\n\nWhat is this paper about? Summarize in 2-3 sentences."}
    ]
)

print("AI Summary:")
print(response.choices[0].message.content)
