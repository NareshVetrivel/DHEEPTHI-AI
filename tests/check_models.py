import os
from dotenv import load_dotenv, find_dotenv
from google import genai

# Automatically find and load the .env file from root directory
env_file_path = find_dotenv()
print(f"[ASTRA Debug]: .env file path -> '{env_file_path}'")

load_dotenv(env_file_path)

# Try fetching from both common variable names
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY_1")

if not api_key:
    print("\n❌ [ERROR]: API Key read aagala! Check if .env file is saved properly.")
    print(f" -> GEMINI_API_KEY: {os.getenv('GEMINI_API_KEY')}")
    print(f" -> GEMINI_API_KEY_1: {os.getenv('GEMINI_API_KEY_1')}")
    exit()

print(f"\n✅ API Key Loaded Successfully: {api_key[:12]}...")

try:
    # Pass explicit API key to Gemini Client
    client = genai.Client(api_key=api_key)
    
    print("\nAvailable Gemini Models:")
    print("=" * 35)
    for model in client.models.list():
        print(f" -> {model.name}")
        
except Exception as e:
    print(f"\n❌ [Gemini API Error]: {e}")