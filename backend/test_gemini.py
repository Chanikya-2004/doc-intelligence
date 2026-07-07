import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 1. Load your .env file
load_dotenv()

# 2. Setup Client
client = genai.Client()

print("\n--- RUNNING DIAGNOSTIC PING ---")

# Test Chat Model (We know this works, but keep it for confirmation)
print("Testing Chat Model...")
chat_response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="Hello Gemini! Pipeline check."
)
print(f"Chat Response: {chat_response.text}\n")

# Test Embedding Model
print("Testing Embedding Model...")
# Use 'text-embedding-004' directly and specify the task type
embed_response = client.models.embed_content(
    model="text-embedding-004",
    contents="Testing our vector pipeline.",
    config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
)

# If this prints 768, you are successful!
print(f"Embedding Vector Dimensions: {len(embed_response.embeddings[0].values)}")
print("-------------------------------\n")