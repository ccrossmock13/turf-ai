import openai
from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

# Your question
question = "Who is Michael Wolpoff?"

print(f"Question: {question}\n")
print("Searching database...")

# Convert question to embedding
response = openai_client.embeddings.create(
    input=question,
    model="text-embedding-3-small"
)
question_embedding = response.data[0].embedding

# Search Pinecone for relevant chunks
results = index.query(vector=question_embedding, top_k=3, include_metadata=True)

print(f"Found {len(results['matches'])} relevant chunks\n")

# Combine the relevant chunks
context = ""
for match in results['matches']:
    context += match['metadata']['text'] + "\n\n"

print("Asking AI to answer based on the research...")

# Ask AI to answer based on the chunks
answer = openai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a turfgrass expert. Answer based ONLY on the provided research text. Cite the source."},
        {"role": "user", "content": f"Research context:\n{context}\n\nQuestion: {question}"}
    ]
)

print("\n=== AI ANSWER ===")
print(answer.choices[0].message.content)
