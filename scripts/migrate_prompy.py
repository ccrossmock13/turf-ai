import os
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone

# Use your existing env vars
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# Define your specific headers from the prompt you shared
headers_to_split_on = [
    ("⚠️", "Safety"),
    ("🎯", "Philosophy"),
    ("11.", "Technical_Chapter"),
    ("11a.", "Technical_Subchapter"),
    ("11b.", "Technical_Subchapter"),
    ("11c.", "Technical_Subchapter")
]

splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
chunks = splitter.split_text(system_prompt) # Your 15,000 line string

# Prepare for Pinecone
vectors = []
for i, chunk in enumerate(chunks):
    # Create the embedding for the chunk
    v_msg = embeddings.embed_query(chunk.page_content)
    
    # Add metadata to distinguish instructions from research
    metadata = chunk.metadata
    metadata["text"] = chunk.page_content
    metadata["source_type"] = "system_instruction" 
    
    vectors.append({
        "id": f"inst_{i}",
        "values": v_msg,
        "metadata": metadata
    })

# Upsert in batches
index.upsert(vectors=vectors)