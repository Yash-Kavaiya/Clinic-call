from datetime import timedelta

from sqlalchemy import select

from app.models import Consent
from app.slot_engine import now_local


def _weekday_with_slots(client, headers):
    day = now_local()
    for offset in range(0, 14):
        date_s = (day + timedelta(days=offset)).strftime("%Y-%m-%d")
        res = client.post(
            "/tools/get_availability",
            headers=headers,
            json={"date": date_s, "language": "gu", "specialty": "gp"},
        )
        assert res.status_code == 200
        if res.json()["count"]:
            return res.json()
    raise AssertionError("no availability")


def test_tool_auth_required(client):
    res = client.post("/tools/lookup_patient", json={"phone": "9876543210"})
    assert res.status_code == 401


def test_lookup_and_consent_and_book(client, tool_headers):
    look = client.post(
        "/tools/lookup_patient",
        headers=tool_headers,
        json={"phone": "9876543210"},
    )
    assert look.status_code == 200
    body = look.json()
    assert body["found"] is True
    assert body["name"] == "Kiran Desai"
    patient_id = body["patient_id"]

    cons = client.post(
        "/tools/log_consent",
        headers=tool_headers,
        json={"phone": "9876543210", "purposes": ["care", "recording", "reminders"]},
    )
    assert cons.status_code == 200

    avail = _weekday_with_slots(client, tool_headers)
    slot = avail["slots"][0]
    booked = client.post(
        "/tools/book_appointment",
        headers=tool_headers,
        json={"patient_id": patient_id, "slot_id": slot["slot_id"], "reason": "toothache"},
    )
    assert booked.status_code == 200, booked.text
    assert booked.json()["booked"] is True
    appt_id = booked.json()["appointment_id"]
    twice = client.post(
        "/tools/book_appointment",
        headers=tool_headers,
        json={"patient_id": patient_id, "slot_id": slot["slot_id"]},
    )
    assert twice.status_code == 409
    cancel = client.post(
        "/tools/cancel_appointment",
        headers=tool_headers,
        json={"appointment_id": appt_id, "reason": "changed plans"},
    )
    assert cancel.json()["cancelled"] is True
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        consents = session.scalars(select(Consent).where(Consent.patient_id == patient_id)).all()
        assert len(consents) >= 3
    finally:
        session.close()


def test_hours_and_emergency(client, tool_headers):
    hours = client.post("/tools/get_clinic_hours", headers=tool_headers, json={"language": "gu"})
    assert hours.status_code == 200
    assert "108" in hours.json()["emergency"]
    em = client.post(
        "/tools/flag_emergency",
        headers=tool_headers,
        json={"reason": "chest pain", "call_sid": "CA123", "phone": "9876543210"},
    )
    assert em.json()["outcome"] == "emergency"
    assert em.json()["end_voicebot"] is True


def test_create_unknown_patient(client, tool_headers):
    res = client.post(
        "/tools/create_patient",
        headers=tool_headers,
        json={"name": "Nita Rana", "phone": "9000011122", "language": "gu", "consent_ids": ["care"]},
    )
    assert res.json()["created"] is True
