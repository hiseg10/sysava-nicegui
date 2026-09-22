import os, sys, json
from pathlib import Path
from dotenv import dotenv_values

env_file = Path(__file__).resolve().parent.parent / ".env"
valores = dotenv_values(str(env_file))
URL = os.environ.get("SUPABASE_URL") or valores.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or valores.get("SUPABASE_SERVICE_ROLE_KEY")

print(f"URL: {URL}")
print(f"KEY: {KEY[:20]}...{KEY[-20:]}")

# Decode JWT payload
import base64
token = KEY.split('.')[1]
# Add padding
token += '=' * (4 - len(token) % 4)
payload = base64.b64decode(token.replace('-', '+').replace('_', '/'))
print(f"JWT payload: {json.loads(payload)}")

# Test connection
try:
    from supabase import create_client
    client = create_client(URL, KEY)
    result = client.from_("users").select("username").limit(1).execute()
    print(f"SUCCESS: {len(result.data)} users found")
except Exception as e:
    print(f"ERROR: {e}")
