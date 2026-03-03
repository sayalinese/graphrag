"""Mini script to invoke /api/chat/session/create via Flask test client."""
from __future__ import annotations

import json
from typing import Any

from app import create_app

app = create_app()
client = app.test_client()

payload = {
    "character_id": "student",
    "name": "test-session",
    "kb_id": None,
    "max_context_length": 10,
}

resp = client.post("/api/chat/session/create", json=payload)
print("Status:", resp.status_code)
print("Body:")
try:
    print(json.dumps(resp.get_json(), ensure_ascii=False, indent=2))
except Exception:
    print(resp.data.decode("utf-8", errors="ignore"))
