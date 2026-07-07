import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not key:
    print("ERROR: No API key found. Check your .env file has GOOGLE_API_KEY or GEMINI_API_KEY set.")
else:
    client = genai.Client(api_key=key)
    print("Models that support generateContent:\n")
    for m in client.models.list():
        if "generateContent" in m.supported_actions:
            print(m.name)