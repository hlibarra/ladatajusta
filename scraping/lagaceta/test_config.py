"""
Test configuration - Verify .env file is loaded correctly
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

print("=" * 60)
print("CONFIGURATION TEST")
print("=" * 60)

# Check .env file exists
if env_path.exists():
    print(f"\n[OK] .env file found at: {env_path}")
else:
    print(f"\n[ERROR] .env file not found at: {env_path}")
    print("Please create a .env file based on .env.example")

# Check database configuration
print("\n--- Database Configuration ---")
print(f"DB_HOST: {os.getenv('DB_HOST', 'localhost')}")
print(f"DB_PORT: {os.getenv('DB_PORT', '5432')}")
print(f"DB_NAME: {os.getenv('DB_NAME', 'ladatajusta')}")
print(f"DB_USER: {os.getenv('DB_USER', 'ladatajusta')}")
print(f"DB_PASSWORD: {'*' * len(os.getenv('DB_PASSWORD', 'ladatajusta'))}")

# Check OpenAI configuration
print("\n--- OpenAI Configuration ---")
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    # Show first 7 chars and last 4 chars
    masked = api_key[:7] + "..." + api_key[-4:] if len(api_key) > 11 else "***"
    print(f"OPENAI_API_KEY: {masked}")
    print(f"OPENAI_MODEL: {os.getenv('OPENAI_MODEL', 'gpt-4o-mini')}")
    print("\n[OK] OpenAI API key is configured")
else:
    print("OPENAI_API_KEY: Not set")
    print("\n[WARNING] OpenAI API key not configured")
    print("AI processing will not work without an API key")
    print("\nTo configure:")
    print("1. Get your API key from: https://platform.openai.com/api-keys")
    print("2. Add it to the .env file: OPENAI_API_KEY=sk-your-key-here")

print("\n" + "=" * 60)
