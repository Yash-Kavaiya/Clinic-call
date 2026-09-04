from datetime import timedelta

from app.slot_engine import now_local


def test_staff_walk_in_and_today(client, staff_token):
    headers = {"Authorization": f"Bearer {staff_token}"}
    doctors = client.get("/staff/doctors", headers=headers)
    assert doctors.status_code == 200
    assert len(doctors.json()) == 2
    day = now_local()
    slots = []
    date_s = ""
    for offset in range(0, 14):
        date_s = (day + timedelta(days=offset)).strftime("%Y-%m-%d")
        avail = client.get(
            f"/staff/availability?date={date_s}&doctor_id={doctors.json()[0]['id']}",
            headers=headers,
        )
        assert avail.status_code == 200
        if avail.json():
            slots = avail.json()
            break
    assert slots
    booked = client.post(
        "/staff/appointments/walk-in",
        headers=headers,
        json={
            "name": "Walk In Patel",
            "phone": "9111122233",
            "slot_id": slots[0]["slot_id"],
            "reason": "walk-in",
        },
    )
    assert booked.status_code == 200, booked.text
    today = client.get(f"/staff/appointments?date={date_s}", headers=headers)
    ids = [row["id"] for row in today.json()]
    assert booked.json()["id"] in ids
    arrived = client.post(
        f"/staff/appointments/{booked.json()['id']}/status",
        headers=headers,
        json={"status": "checked_in"},
    )
    assert arrived.json()["status"] == "checked_in"
    calls = client.get("/staff/calls", headers=headers)
    assert calls.status_code == 200
    mode = client.post(
        "/staff/clinic/voice-mode",
        headers=headers,
        json={"voice_mode": "human"},
    )
    assert mode.json()["voice_mode"] == "human"
