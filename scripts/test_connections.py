import sys
from pathlib import Path
import requests

# Ensure src is in PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config, DEFAULT_SERVER_URL
from src.firebase_auth import FirebaseAuth
from src.firebase_crud import FirebaseCRUD

def test_opencode(server_url: str):
    print(f"Testing OpenCode LLM at {server_url}...")
    try:
        resp = requests.get(server_url, timeout=5)
        print(f"  [OK] Server responded with status code {resp.status_code}.")
    except requests.exceptions.RequestException as e:
        print(f"  [WARN] Could not connect to OpenCode. Is 'opencode serve' running? Error: {e}")

def test_firebase_api_key():
    print("Testing Firebase Auth API Key presence...")
    try:
        auth = FirebaseAuth()
        if not auth._api_key or auth._api_key.startswith("your-"):
            print(f"  [WARN] Firebase API key is missing or a placeholder: '{auth._api_key}'")
        else:
            print("  [OK] Firebase API key found in config.")
    except Exception as e:
        print(f"  [ERROR] {e}")

def test_firebase_credentials():
    print("Testing Firebase service account credentials...")
    try:
        crud = FirebaseCRUD()
        crud._ensure_client()
        if crud.client:
            print("  [OK] Firebase service account credentials loaded and client initialized.")
        else:
            print("  [WARN] Firebase client could not be initialized. Missing credentials file?")
    except Exception as e:
        print(f"  [WARN] Could not initialize Firebase: {e}")

from src.opencode_serve_manager import ensure_opencode_serve_running, stop_opencode_serve

if __name__ == "__main__":
    print("--- Daemon Connection Test Utility ---")
    cfg = load_config()
    opencode_url = cfg.get("llm", {}).get("server_url", "http://127.0.0.1:4096")
    
    print("Starting local opencode server...")
    if ensure_opencode_serve_running(url=opencode_url):
        print("  [OK] OpenCode server started or is already running.")
    else:
        print("  [WARN] Failed to start OpenCode server.")
        
    test_opencode(opencode_url)
    print()
    test_firebase_api_key()
    print()
    test_firebase_credentials()
    
    print("\nStopping local opencode server...")
    stop_opencode_serve()
    print("--- Test Complete ---")
