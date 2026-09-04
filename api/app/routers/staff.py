from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.audit import audit
from app.auth import create_token, verify_password
from app.database import get_db
from app.deps import current_user
from app.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    Branch,
    CallSession,
    Clinic,
    DoctorProfile,
    Patient,
    User,
)
from app.slot_engine import book_appointment, now_local, set_status
from app.speakable import parse_slot_id

router = APIRouter(prefix="/staff", tags=["staff"])


class LoginIn(BaseModel):
    email: str
    password: str


class WalkInIn(BaseModel):
    patient_id: int | None = None
    name: str | None = None
    phone: str | None = None
    language: str = "gu"
    slot_id: str
    reason: str = "walk-in"


class StatusIn(BaseModel):
    status: str


class VoiceModeIn(BaseModel):
    voice_mode: str


class PatientIn(BaseModel):
    name: str
    phone: str
    language: str = "gu"
    dob: str | None = None
    sex: str | None = None


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == body.email)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="bad credentials")
    return {
        "token": create_token(user.id, user.email, user.role),
        "name": user.name,
        "role": user.role,
        "email": user.email,
    }


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "role": user.role, "email": user.email}


@router.get("/clinic")
def clinic_settings(db: Session = Depends(get_db), _: User = Depends(current_user)):
    clinic = db.scalars(select(Clinic)).first()
    branch = db.scalars(select(Branch)).first()
    return {
        "id": clinic.id,
        "name": clinic.name,
        "voice_mode": clinic.voice_mode,
        "recording_retention_days": clinic.recording_retention_days,
        "branch": {
            "id": branch.id,
            "name": branch.name,
            "address": branch.address,
            "hours": branch.hours_json,
            "maps_url": branch.maps_url,
        },
    }


@router.post("/clinic/voice-mode")
def set_voice_mode(body: VoiceModeIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if body.voice_mode not in {"bot", "human"}:
        raise HTTPException(status_code=400, detail="voice_mode must be bot or human")
    clinic = db.scalars(select(Clinic)).first()
    before = clinic.voice_mode
    clinic.voice_mode = body.voice_mode
    audit(db, user.email, "voice_mode", before={"voice_mode": before}, after={"voice_mode": body.voice_mode})
    db.commit()
    return {"voice_mode": clinic.voice_mode}


@router.get("/availability")
def staff_availability(
    date: str,
    doctor_id: int | None = None,
    specialty: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    from app.slot_engine import availability

    return availability(db, date_s=date, doctor_id=doctor_id, specialty=specialty, language="en", limit=24)


@router.get("/doctors")
def list_doctors(db: Session = Depends(get_db), _: User = Depends(current_user)):
    doctors = db.scalars(select(DoctorProfile)).all()
    return [
        {
            "id": d.id,
            "name": d.display_name,
            "specialties": d.specialties,
            "consult_minutes": d.consult_minutes,
            "fee": d.fee,
        }
        for d in doctors
    ]


@router.get("/patients")
def search_patients(phone: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    q = select(Patient)
    if phone:
        digits = "".join(c for c in phone if c.isdigit())
        q = q.where(Patient.phone.contains(digits[-10:] if len(digits) >= 10 else digits))
    rows = db.scalars(q.limit(50)).all()
    return [
        {"id": p.id, "name": p.name, "phone": p.phone, "language": p.language, "abha_id": p.abha_id}
        for p in rows
    ]


@router.post("/patients")
def create_patient(body: PatientIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    clinic = db.scalars(select(Clinic)).first()
    digits = "".join(c for c in body.phone if c.isdigit())
    phone = "+91" + digits[-10:] if len(digits) >= 10 else body.phone
    existing = db.scalars(select(Patient).where(Patient.phone == phone)).first()
    if existing:
        return {"id": existing.id, "created": False}
    patient = Patient(
        clinic_id=clinic.id,
        name=body.name,
        phone=phone,
        language=body.language,
        dob=body.dob,
        sex=body.sex,
    )
    db.add(patient)
    audit(db, user.email, "create_patient", after={"phone": phone})
    db.commit()
    db.refresh(patient)
    return {"id": patient.id, "created": True}


@router.get("/appointments")
def today_appointments(
    date: str | None = None,
    doctor_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    day = datetime.strptime(date, "%Y-%m-%d") if date else now_local()
    start = datetime(day.year, day.month, day.day)
    end = start + timedelta(days=1)
    q = (
        select(Appointment)
        .options(joinedload(Appointment.patient), joinedload(Appointment.doctor))
        .where(Appointment.slot_start >= start, Appointment.slot_start < end)
        .order_by(Appointment.slot_start)
    )
    if doctor_id:
        q = q.where(Appointment.doctor_id == doctor_id)
    rows = db.scalars(q).unique().all()
    return [
        {
            "id": a.id,
            "status": a.status,
            "source": a.source,
            "reason": a.reason,
            "slot_start": a.slot_start.isoformat(timespec="minutes"),
            "slot_end": a.slot_end.isoformat(timespec="minutes"),
            "patient": {"id": a.patient.id, "name": a.patient.name, "phone": a.patient.phone},
            "doctor": {"id": a.doctor_id, "name": a.doctor.display_name},
        }
        for a in rows
    ]


@router.get("/appointments/{appointment_id}")
def appointment_detail(appointment_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    a = db.scalars(
        select(Appointment)
        .options(joinedload(Appointment.patient), joinedload(Appointment.doctor))
        .where(Appointment.id == appointment_id)
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="not_found")
    return {
        "id": a.id,
        "status": a.status,
        "source": a.source,
        "reason": a.reason,
        "slot_start": a.slot_start.isoformat(timespec="minutes"),
        "patient": {"id": a.patient.id, "name": a.patient.name, "phone": a.patient.phone},
        "doctor": {"id": a.doctor_id, "name": a.doctor.display_name},
    }


@router.post("/appointments/walk-in")
def walk_in(body: WalkInIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    clinic = db.scalars(select(Clinic)).first()
    patient_id = body.patient_id
    if not patient_id:
        if not body.name or not body.phone:
            raise HTTPException(status_code=400, detail="name_and_phone_required")
        digits = "".join(c for c in body.phone if c.isdigit())
        phone = "+91" + digits[-10:]
        patient = db.scalars(select(Patient).where(Patient.phone == phone)).first()
        if not patient:
            patient = Patient(clinic_id=clinic.id, name=body.name, phone=phone, language=body.language)
            db.add(patient)
            db.flush()
        patient_id = patient.id
    doctor_id, start = parse_slot_id(body.slot_id)
    try:
        appt = book_appointment(
            db,
            patient_id=patient_id,
            doctor_id=doctor_id,
            slot_start=start,
            reason=body.reason,
            source=AppointmentSource.walkin.value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit(db, user.email, "walk_in", after={"appointment_id": appt.id})
    db.commit()
    db.refresh(appt)
    return {"id": appt.id, "status": appt.status}


@router.post("/appointments/{appointment_id}/status")
def update_status(appointment_id: int, body: StatusIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    allowed = {s.value for s in AppointmentStatus}
    if body.status not in allowed:
        raise HTTPException(status_code=400, detail="bad status")
    try:
        appt = set_status(db, appointment_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit(db, user.email, "set_status", after={"id": appointment_id, "status": body.status})
    db.commit()
    return {"id": appt.id, "status": appt.status}


@router.get("/calls")
def list_calls(db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.scalars(select(CallSession).order_by(CallSession.created_at.desc()).limit(100)).all()
    return [
        {
            "id": c.id,
            "exotel_sid": c.exotel_sid,
            "sarvam_conv_id": c.sarvam_conv_id,
            "from_phone": c.from_phone,
            "outcome": c.outcome,
            "agent_name": c.agent_name,
            "duration_sec": c.duration_sec,
            "recording_url": c.recording_url,
            "created_at": c.created_at.isoformat(),
            "patient_id": c.patient_id,
        }
        for c in rows
    ]


@router.get("/calls/{call_id}")
def call_detail(call_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    c = db.get(CallSession, call_id)
    if not c:
        raise HTTPException(status_code=404, detail="not_found")
    return {
        "id": c.id,
        "exotel_sid": c.exotel_sid,
        "from_phone": c.from_phone,
        "outcome": c.outcome,
        "recording_url": c.recording_url,
        "transfer_reason": c.transfer_reason,
        "utterances": [
            {"role": u.role, "text": u.text, "lang": u.lang, "ts": u.ts.isoformat()} for u in c.utterances
        ],
    }
