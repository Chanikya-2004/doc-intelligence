import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not key:
    print("ERROR: No API key found. Check your .env file.")
    raise SystemExit(1)

client = genai.Client(api_key=key)

candidates = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-flash-latest",
    "gemini-1.5-flash",
]

for name in candidates:
    try:
        resp = client.models.generate_content(
            model=name,
            contents="Say OK",
        )
        print(f"WORKS  -> {name}  | response: {resp.text.strip()[:40]}")
    except Exception as e:
        msg = str(e)
        print(f"FAILS  -> {name}  | {msg[:120]}")