import sys
from pathlib import Path
import requests

# Ensure src is in PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config, DEFAULT_SERVER_URL

def check_opencode(server_url: str):
    print(f"Testing OpenCode LLM at {server_url}...")
    try:
        resp = requests.get(server_url, timeout=5)
        print(f"  [OK] Server responded with status code {resp.status_code}.")
    except requests.exceptions.RequestException as e:
        print(f"  [WARN] Could not connect to OpenCode. Is 'opencode serve' running? Error: {e}")

def test_firebase_backend(backend_url: str):
    print("Testing Daemon auth backend...")
    if not backend_url:
        print("  [WARN] Firebase cloud sync is offline; configure firebase.auth_backend_url.")
        return
    try:
        resp = requests.get(f"{backend_url.rstrip('/')}/health", timeout=5)
        if resp.status_code == 200:
            print("  [OK] Daemon auth backend is reachable.")
        else:
            print(f"  [WARN] Backend /health returned HTTP {resp.status_code}.")
    except requests.exceptions.RequestException as e:
        print(f"  [WARN] Could not reach Daemon auth backend: {e}")

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
        
    check_opencode(opencode_url)
    print()
    test_firebase_backend(cfg.get("firebase", {}).get("auth_backend_url", ""))
    
    print("\nStopping local opencode server...")
    stop_opencode_serve()
    print("--- Test Complete ---")
