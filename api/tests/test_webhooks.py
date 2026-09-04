from sqlalchemy import select

from app.models import CallSession, CallUtterance, Consent


def test_sarvam_on_start_known_patient(client):
    res = client.post(
        "/webhooks/sarvam/on-start",
        json={"from_phone": "+919876543210", "call_sid": "CA-start-1", "conversation_id": "conv-1"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["found"] is True
    assert body["name"] == "Kiran Desai"
    assert body["route"] == "bot"
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        consents = session.scalars(select(Consent)).all()
        assert any(c.purpose == "recording" for c in consents)
    finally:
        session.close()


def test_exotel_status_and_transcript(client):
    client.post(
        "/webhooks/sarvam/on-start",
        json={"From": "9876543210", "CallSid": "CA-ex-1"},
    )
    res = client.post(
        "/webhooks/exotel/status",
        json={
            "CallSid": "CA-ex-1",
            "RecordingUrl": "https://recordings.exotel.in/x.mp3",
            "Duration": "42",
            "From": "9876543210",
            "Status": "completed",
        },
    )
    assert res.json()["ok"] is True
    client.post(
        "/webhooks/sarvam/transcript",
        json={"call_sid": "CA-ex-1", "role": "user", "text": "Mane appointment joie", "lang": "gu"},
    )
    client.post(
        "/webhooks/sarvam/on-end",
        json={
            "call_sid": "CA-ex-1",
            "outcome": "booked",
            "utterances": [{"role": "bot", "text": "Confirm karo", "lang": "gu"}],
        },
    )
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        row = session.scalars(select(CallSession).where(CallSession.exotel_sid == "CA-ex-1")).first()
        assert row.recording_url.endswith(".mp3")
        assert row.duration_sec == 42
        utts = session.scalars(select(CallUtterance).where(CallUtterance.session_id == row.id)).all()
        assert len(utts) >= 2
    finally:
        session.close()


def test_kill_switch_on_start(client, staff_token):
    res = client.post(
        "/staff/clinic/voice-mode",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"voice_mode": "human"},
    )
    assert res.json()["voice_mode"] == "human"
    start = client.post(
        "/webhooks/sarvam/on-start",
        json={"from_phone": "9876543210", "call_sid": "CA-human"},
    )
    assert start.json()["route"] == "human"
