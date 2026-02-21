import openai
import os
from dotenv import load_dotenv

load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("Asking AI about dollar spot...")

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "What causes dollar spot in turfgrass? Answer in 2-3 sentences."}
    ]
)

print("\nAI Response:")
print(response.choices[0].message.content)


