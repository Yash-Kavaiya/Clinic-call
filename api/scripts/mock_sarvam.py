import json
import os
import sys
from datetime import timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.slot_engine import now_local  # noqa: E402

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
KEY = os.environ.get("TOOL_API_KEY", "dev-tool-key")


def post(path, payload):
    r = httpx.post(f"{BASE}{path}", json=payload, headers={"X-Tool-Key": KEY}, timeout=10)
    r.raise_for_status()
    return r.json()


def main():
    look = post("/tools/lookup_patient", {"phone": "9876543210"})
    print("lookup", look)
    day = now_local()
    avail = None
    for i in range(14):
        date_s = (day + timedelta(days=i)).strftime("%Y-%m-%d")
        avail = post("/tools/get_availability", {"date": date_s, "language": "gu", "specialty": "gp"})
        if avail["count"]:
            break
    print("availability", json.dumps(avail, indent=2))
    slot = avail["slots"][0]
    booked = post(
        "/tools/book_appointment",
        {"patient_id": look["patient_id"], "slot_id": slot["slot_id"], "reason": "mock"},
    )
    print("booked", booked)


if __name__ == "__main__":
    main()
