"""Ping Sarvam and Exotel using env credentials. Prints status codes only."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402


def _snip(text: str, n: int = 180) -> str:
    return " ".join((text or "").split())[:n]


def _exotel_code(text: str) -> str:
    if "34010" in text:
        return "34010_bad_key_or_token"
    if "34009" in text:
        return "34009_auth_ok_bad_or_missing_sid"
    if "Accounts or account_sid" in text:
        return "missing_account_sid"
    return _snip(text)


def check_sarvam() -> None:
    key = settings.sarvam_api_key
    if not key:
        print("sarvam: SKIP missing SARVAM_API_KEY")
        return
    r = httpx.post(
        "https://api.sarvam.ai/translate",
        headers={"api-subscription-key": key, "Content-Type": "application/json"},
        json={
            "input": "hello",
            "source_language_code": "en-IN",
            "target_language_code": "hi-IN",
        },
        timeout=30,
    )
    print(f"sarvam_models: HTTP {r.status_code}")
    if r.status_code >= 400:
        print(" ", _snip(r.text))
    else:
        print(" ", "ok")
    print("sarvam_voice_agents: needs org_id + workspace_id from indus.sarvam.ai URL")
    print(" ", "model sk_ key is not enough to list orgs (no public /orgs index)")


def check_exotel() -> None:
    key = settings.exotel_api_key
    token = settings.exotel_api_token
    sid = settings.exotel_account_sid
    if not (key and token):
        print("exotel: SKIP missing EXOTEL_API_KEY / EXOTEL_API_TOKEN")
        return
    auth = (key, token)
    hosts = ["https://api.exotel.com", "https://api.in.exotel.com"]
    for base in hosts:
        host = base.split("//", 1)[1]
        path_sid = sid or "NEED_ACCOUNT_SID"
        url = f"{base}/v1/Accounts/{path_sid}.json"
        r = httpx.get(url, auth=auth, timeout=20)
        print(f"exotel {host} sid={bool(sid)}: HTTP {r.status_code} {_exotel_code(r.text)}")


if __name__ == "__main__":
    print("sarvam_key_configured", bool(settings.sarvam_api_key))
    print("exotel_key_configured", bool(settings.exotel_api_key and settings.exotel_api_token))
    print("exotel_sid_configured", bool(settings.exotel_account_sid))
    check_sarvam()
    check_exotel()
