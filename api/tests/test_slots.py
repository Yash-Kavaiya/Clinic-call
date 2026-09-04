from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Appointment, AppointmentStatus, DoctorProfile, Patient
from app.slot_engine import availability, book_appointment, hold_slot, now_local
from app.speakable import parse_slot_id


def _next_slot(db, doctor_id=None):
    day = now_local()
    for offset in range(0, 14):
        date_s = (day + timedelta(days=offset)).strftime("%Y-%m-%d")
        slots = availability(db, date_s=date_s, doctor_id=doctor_id, language="en", limit=3)
        if slots:
            return slots[0]
    raise AssertionError("no slots in next 14 days")


def test_availability_max_three(db):
    slot = _next_slot(db)
    day = slot["slot_start"][:10]
    slots = availability(db, date_s=day, language="en", limit=3)
    assert 1 <= len(slots) <= 3
    assert "speak_time" in slots[0]
    assert "17:00" not in slots[0]["speak_time"]


def test_book_only_offered_slot(db):
    patient = db.scalars(select(Patient)).first()
    doctor = db.scalars(select(DoctorProfile)).first()
    fake = now_local().replace(hour=3, minute=0, second=0, microsecond=0)
    try:
        book_appointment(db, patient_id=patient.id, doctor_id=doctor.id, slot_start=fake)
        db.commit()
        assert False, "should reject"
    except ValueError as exc:
        assert "slot_not_available" in str(exc)


def test_book_and_unique_constraint(db):
    patients = db.scalars(select(Patient)).all()
    ids = [p.id for p in patients]
    slot = _next_slot(db)
    doctor_id, start = parse_slot_id(slot["slot_id"])
    book_appointment(db, patient_id=ids[0], doctor_id=doctor_id, slot_start=start)
    db.commit()
    db.close()
    db2 = SessionLocal()
    try:
        book_appointment(db2, patient_id=ids[1], doctor_id=doctor_id, slot_start=start)
        db2.commit()
        assert False, "second book should fail"
    except ValueError as exc:
        assert str(exc) in {"slot_taken", "slot_not_available"}
    finally:
        db2.close()


def test_hold_then_book(db):
    patient = db.scalars(select(Patient)).first()
    slot = _next_slot(db)
    doctor_id, start = parse_slot_id(slot["slot_id"])
    held = hold_slot(db, patient_id=patient.id, doctor_id=doctor_id, slot_start=start)
    db.commit()
    assert held.status == AppointmentStatus.held.value
    booked = book_appointment(
        db,
        patient_id=patient.id,
        doctor_id=doctor_id,
        slot_start=start,
        hold_id=held.id,
    )
    db.commit()
    assert booked.status == AppointmentStatus.booked.value
    assert booked.id == held.id


def test_parallel_book_one_wins(db):
    patients = db.scalars(select(Patient)).all()
    ids = [p.id for p in patients]
    slot = _next_slot(db)
    doctor_id, start = parse_slot_id(slot["slot_id"])
    db.rollback()
    db.close()

    def attempt(patient_id: int) -> str:
        session = SessionLocal()
        try:
            book_appointment(
                session, patient_id=patient_id, doctor_id=doctor_id, slot_start=start
            )
            session.commit()
            return "ok"
        except ValueError:
            session.rollback()
            return "fail"
        except Exception:
            session.rollback()
            return "fail"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(attempt, pid) for pid in ids[:2]]
        results = [f.result() for f in as_completed(futs)]
    assert results.count("ok") == 1
    assert results.count("fail") == 1
    check = SessionLocal()
    try:
        active = check.scalars(
            select(Appointment).where(
                Appointment.doctor_id == doctor_id,
                Appointment.slot_start == start,
                Appointment.status.in_(
                    [
                        AppointmentStatus.held.value,
                        AppointmentStatus.booked.value,
                        AppointmentStatus.confirmed.value,
                        AppointmentStatus.checked_in.value,
                    ]
                ),
            )
        ).all()
        assert len(active) == 1
    finally:
        check.close()
