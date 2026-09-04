import hashlib
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.audit import audit
from app.config import settings
from app.database import get_db
from app.models import (
    Appointment,
    AppointmentSource,
    Branch,
    CallSession,
    Clinic,
    Consent,
    ConsentPurpose,
    DoctorProfile,
    Patient,
)
from app.slot_engine import (
    availability,
    book_appointment,
    cancel_appointment,
    hold_slot,
    now_local,
    open_appointments,
)
from app.speakable import parse_slot_id, speak_day, speak_time

router = APIRouter(prefix="/tools", tags=["tools"])


def _check_tool_auth(
    request_body: bytes,
    x_tool_key: str | None,
    x_tool_signature: str | None,
) -> None:
    if x_tool_key != settings.tool_api_key:
        raise HTTPException(status_code=401, detail="bad tool key")
    if x_tool_signature:
        digest = hmac.new(
            settings.tool_hmac_secret.encode(), request_body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(digest, x_tool_signature):
            raise HTTPException(status_code=401, detail="bad hmac")


async def require_tool(
    request: Request,
    x_tool_key: str | None = Header(default=None),
    x_tool_signature: str | None = Header(default=None),
) -> None:
    body = await request.body()
    _check_tool_auth(body, x_tool_key, x_tool_signature)


class LookupIn(BaseModel):
    phone: str
    call_sid: str | None = None


class CreatePatientIn(BaseModel):
    name: str
    phone: str
    language: str = "gu"
    consent_ids: list[str] = []


class ConsentIn(BaseModel):
    phone: str
    purposes: list[str]
    channel: str = "voice"
    call_sid: str | None = None


class HoursIn(BaseModel):
    branch_id: int | None = None
    language: str = "gu"


class AvailabilityIn(BaseModel):
    date: str
    doctor_id: int | None = None
    specialty: str | None = None
    branch_id: int | None = None
    language: str = "gu"


class HoldIn(BaseModel):
    patient_id: int
    slot_id: str
    reason: str = ""


class BookIn(BaseModel):
    patient_id: int
    slot_id: str
    reason: str = ""
    hold_id: int | None = None


class CancelIn(BaseModel):
    appointment_id: int
    reason: str = ""


class StatusIn(BaseModel):
    phone: str | None = None
    appointment_id: int | None = None
    language: str = "gu"


class TransferIn(BaseModel):
    reason: str
    department: str = "reception"
    call_sid: str | None = None
    phone: str | None = None


def _normalize_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 10:
        return "+91" + digits
    if phone.startswith("+"):
        return "+" + digits
    return "+" + digits if digits else phone


def _patient_by_phone(db: Session, phone: str) -> Patient | None:
    return db.scalars(select(Patient).where(Patient.phone == _normalize_phone(phone))).first()


def _clinic(db: Session) -> Clinic:
    clinic = db.scalars(select(Clinic)).first()
    if not clinic:
        raise HTTPException(status_code=500, detail="clinic_not_seeded")
    return clinic


def _appt_speak(appt: Appointment, language: str) -> dict:
    return {
        "appointment_id": appt.id,
        "status": appt.status,
        "doctor": appt.doctor.display_name if appt.doctor else "",
        "speak_day": speak_day(appt.slot_start, language),
        "speak_time": speak_time(appt.slot_start, language),
        "slot_id": f"{appt.doctor_id}:{appt.slot_start.strftime('%Y%m%dT%H%M')}",
    }


@router.post("/lookup_patient")
def lookup_patient(body: LookupIn, db: Session = Depends(get_db), _: None = Depends(require_tool)):
    patient = _patient_by_phone(db, body.phone)
    clinic = _clinic(db)
    route = "human" if clinic.voice_mode == "human" else "bot"
    if not patient:
        audit(db, "voice", "lookup_patient", after={"found": False, "phone": _normalize_phone(body.phone)})
        db.commit()
        return {
            "found": False,
            "phone": _normalize_phone(body.phone),
            "route": route,
            "voice_mode": clinic.voice_mode,
        }
    last = db.scalars(
        select(Appointment)
        .where(Appointment.patient_id == patient.id)
        .order_by(Appointment.slot_start.desc())
    ).first()
    open_appts = [_appt_speak(a, patient.language) for a in open_appointments(db, patient.id)]
    audit(db, "voice", "lookup_patient", after={"found": True, "patient_id": patient.id})
    db.commit()
    return {
        "found": True,
        "patient_id": patient.id,
        "name": patient.name,
        "language": patient.language,
        "last_visit": last.slot_start.date().isoformat() if last else None,
        "open_appts": open_appts,
        "route": route,
        "voice_mode": clinic.voice_mode,
    }


@router.post("/create_patient")
def create_patient(body: CreatePatientIn, db: Session = Depends(get_db), _: None = Depends(require_tool)):
    clinic = _clinic(db)
    phone = _normalize_phone(body.phone)
    existing = _patient_by_phone(db, phone)
    if existing:
        return {"created": False, "patient_id": existing.id, "name": existing.name}
    patient = Patient(
        clinic_id=clinic.id,
        phone=phone,
        name=body.name,
        language=body.language,
    )
    db.add(patient)
    db.flush()
    for purpose in body.consent_ids or []:
        db.add(
            Consent(
                patient_id=patient.id,
                purpose=purpose,
                channel="voice",
                version="v1",
                granted_at=now_local(),
            )
        )
    audit(db, "voice", "create_patient", after={"patient_id": patient.id, "phone": phone})
    db.commit()
    db.refresh(patient)
    return {"created": True, "patient_id": patient.id, "name": patient.name, "language": patient.language}


@router.post("/log_consent")
def log_consent(body: ConsentIn, db: Session = Depends(get_db), _: None = Depends(require_tool)):
    patient = _patient_by_phone(db, body.phone)
    if not patient:
        raise HTTPException(status_code=404, detail="patient_not_found")
    saved = []
    for purpose in body.purposes:
        if purpose not in {p.value for p in ConsentPurpose}:
            continue
        row = Consent(
            patient_id=patient.id,
            purpose=purpose,
            channel=body.channel,
            version="v1",
            granted_at=now_local(),
        )
        db.add(row)
        db.flush()
        saved.append(row.id)
    audit(db, "voice", "log_consent", after={"patient_id": patient.id, "purposes": body.purposes})
    db.commit()
    return {"ok": True, "consent_ids": saved, "speak": "Consent nondhayu."}


@router.post("/get_clinic_hours")
def get_clinic_hours(body: HoursIn, db: Session = Depends(get_db), _: None = Depends(require_tool)):
    q = select(Branch)
    if body.branch_id:
        q = q.where(Branch.id == body.branch_id)
    branch = db.scalars(q).first()
    if not branch:
        raise HTTPException(status_code=404, detail="branch_not_found")
    clinic = _clinic(db)
    return {
        "branch": branch.name,
        "address": branch.address,
        "maps": branch.maps_url,
        "hours": branch.hours_json,
        "speak_hours": "Savaar na nav thi ek, shaame na saat thi vis. Shanivaar subah. Ravivaar bandh.",
        "after_hours": branch.after_hours_message,
        "emergency": "Emergency hoy to 108 ke nearest hospital.",
        "voice_mode": clinic.voice_mode,
        "consent_notice": {
            "gu": clinic.consent_notice_gu,
            "hi": clinic.consent_notice_hi,
            "en": clinic.consent_notice_en,
        }.get(body.language[:2], clinic.consent_notice_en),
    }


@router.post("/get_availability")
def get_availability(body: AvailabilityIn, db: Session = Depends(get_db), _: None = Depends(require_tool)):
    slots = availability(
        db,
        date_s=body.date,
        doctor_id=body.doctor_id,
        specialty=body.specialty,
        branch_id=body.branch_id,
        language=body.language,
        limit=3,
    )
    audit(db, "voice", "get_availability", after={"date": body.date, "count": len(slots)})
    db.commit()
    speakable = [f"{s['doctor_name']}, {s['speak_day']}, {s['speak_time']}" for s in slots]
    return {"slots": slots, "speak_options": speakable, "count": len(slots)}


@router.post("/hold_slot")
def hold_slot_tool(body: HoldIn, db: Session = Depends(get_db), _: None = Depends(require_tool)):
    doctor_id, start = parse_slot_id(body.slot_id)
    try:
        appt = hold_slot(
            db,
            patient_id=body.patient_id,
            doctor_id=doctor_id,
            slot_start=start,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit(db, "voice", "hold_slot", after={"appointment_id": appt.id, "slot_id": body.slot_id})
    db.commit()
    db.refresh(appt)
    return {
        "held": True,
        "appointment_id": appt.id,
        "hold_seconds": settings.hold_seconds,
        "speak": f"Slot hold. Confirm karo: {speak_time(start, 'gu')}",
    }


@router.post("/book_appointment")
def book_appointment_tool(body: BookIn, db: Session = Depends(get_db), _: None = Depends(require_tool)):
    doctor_id, start = parse_slot_id(body.slot_id)
    try:
        appt = book_appointment(
            db,
            patient_id=body.patient_id,
            doctor_id=doctor_id,
            slot_start=start,
            reason=body.reason,
            hold_id=body.hold_id,
            source=AppointmentSource.voice.value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    doctor = db.get(DoctorProfile, doctor_id)
    audit(db, "voice", "book_appointment", after={"appointment_id": appt.id, "slot_id": body.slot_id})
    db.commit()
    db.refresh(appt)
    return {
        "booked": True,
        "appointment_id": appt.id,
        "doctor": doctor.display_name if doctor else "",
        "speak_day": speak_day(start, "gu"),
        "speak_time": speak_time(start, "gu"),
        "speak": (
            f"Nondhayu. {doctor.display_name if doctor else ''} "
            f"{speak_day(start, 'gu')} {speak_time(start, 'gu')}."
        ),
        "sms_hint": "SMS ma token ane map pin aavse.",
    }


@router.post("/cancel_appointment")
def cancel_appointment_tool(body: CancelIn, db: Session = Depends(get_db), _: None = Depends(require_tool)):
    try:
        appt = cancel_appointment(db, body.appointment_id, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit(db, "voice", "cancel_appointment", after={"appointment_id": appt.id, "reason": body.reason})
    db.commit()
    return {"cancelled": True, "appointment_id": appt.id, "speak": "Appointment cancel thai gayu."}


@router.post("/get_appointment_status")
def get_appointment_status(body: StatusIn, db: Session = Depends(get_db), _: None = Depends(require_tool)):
    if body.appointment_id:
        appt = db.scalars(
            select(Appointment).options(joinedload(Appointment.doctor)).where(Appointment.id == body.appointment_id)
        ).first()
        if not appt:
            raise HTTPException(status_code=404, detail="not_found")
        return _appt_speak(appt, body.language)
    if not body.phone:
        raise HTTPException(status_code=400, detail="phone_or_id_required")
    patient = _patient_by_phone(db, body.phone)
    if not patient:
        return {"found": False}
    appts = open_appointments(db, patient.id)
    return {"found": True, "appointments": [_appt_speak(a, body.language) for a in appts]}


def _transfer(db: Session, reason: str, outcome: str, call_sid: str | None, phone: str | None) -> dict:
    session = None
    if call_sid:
        session = db.scalars(select(CallSession).where(CallSession.exotel_sid == call_sid)).first()
    if not session:
        session = CallSession(
            exotel_sid=call_sid,
            from_phone=_normalize_phone(phone) if phone else "",
            direction="inbound",
            agent_name="receptionist",
        )
        db.add(session)
        db.flush()
    session.outcome = outcome
    session.transfer_reason = reason
    audit(db, "voice", outcome, after={"reason": reason, "call_sid": call_sid})
    db.commit()
    return {
        "transfer": True,
        "end_voicebot": True,
        "outcome": outcome,
        "speak": "Receptionist saathe jodu chhu.",
        "exotel_next": "connect_hunt_group",
    }


@router.post("/transfer_to_human")
def transfer_to_human(body: TransferIn, db: Session = Depends(get_db), _: None = Depends(require_tool)):
    return _transfer(db, body.reason, "transfer", body.call_sid, body.phone)


@router.post("/flag_emergency")
def flag_emergency(body: TransferIn, db: Session = Depends(get_db), _: None = Depends(require_tool)):
    result = _transfer(db, body.reason, "emergency", body.call_sid, body.phone)
    result["speak"] = "Emergency. 108 ke receptionist saathe jodae. Diagnosis nathi."
    return result
