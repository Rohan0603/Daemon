#!/usr/bin/env py
"""Wipe all Firestore data for the current user/pet and local auth tokens.
Run this to start completely fresh with memory."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import requests
from pathlib import Path

from src.firebase_auth import FirebaseAuth
from src.config import load_config

def wipe_firestore():
    config = load_config(validate=False)
    firebase_cfg = config.get("firebase", {})
    api_key = firebase_cfg.get("api_key")
    project_id = firebase_cfg.get("project_id")
    auth_backend_url = firebase_cfg.get("auth_backend_url")

    # Load saved auth
    auth_path = Path("data/.daemon_auth.json")
    if not auth_path.exists():
        print("No local auth file found")
        return

    auth_data = json.loads(auth_path.read_text())
    uid = auth_data.get("uid")
    id_token = auth_data.get("idToken")
    refresh_token = auth_data.get("refreshToken")

    if not (uid and id_token):
        print("No valid auth tokens found")
        return

    print(f"Wiping Firestore for user: {uid}")

    # Wipe collections via Firestore REST API
    headers = {"Authorization": f"Bearer {id_token}", "Content-Type": "application/json"}
    base = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"

    collections_to_wipe = [
        f"users/{uid}/pets/kenny",           # core_brain document
        f"users/{uid}/pets/kenny/memories",  # vector memories
        f"users/{uid}/pets/kenny/diary",     # diary entries
        f"users/{uid}",                      # user document
    ]

    for coll in collections_to_wipe:
        url = f"{base}/{coll}"
        # Delete document
        resp = requests.delete(url, headers=headers)
        print(f"DELETE {coll}: {resp.status_code}")
        # Also try to delete all documents in collection (runQuery + batch delete)
        if "memories" in coll or "diary" in coll:
            # List all docs
            query_resp = requests.post(
                f"{base}:runQuery",
                headers=headers,
                json={"structuredQuery": {"from": [{"collectionId": coll.split("/")[-1]}]}}
            )
            if query_resp.status_code == 200:
                for row in query_resp.json():
                    doc = row.get("document", {})
                    name = doc.get("name", "")
                    if name:
                        doc_id = name.split("/")[-1]
                        del_resp = requests.delete(f"{base}/{coll}/{doc_id}", headers=headers)
                        print(f"  DELETE {coll}/{doc_id}: {del_resp.status_code}")

    # Clear local auth
    auth_path.unlink(missing_ok=True)
    print("Deleted local auth tokens")

    # Clear local memory/diary caches
    for f in [".daemon_memory.json", ".daemon_history.json", ".daemon_diary.json", ".daemon_response_cache.json", ".daemon_state.json"]:
        Path(f"data/{f}").unlink(missing_ok=True)
    print("Cleared local cache files")

    print("\n✅ Fresh start complete. Next run will trigger onboarding.")

if __name__ == "__main__":
    wipe_firestore()