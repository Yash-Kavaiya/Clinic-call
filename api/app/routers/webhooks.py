from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import settings
from app.database import get_db
from app.models import CallSession, CallUtterance, Clinic, Consent, Patient
from app.slot_engine import now_local, open_appointments
from app.speakable import speak_day, speak_time
from app.timeutil import utcnow

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _normalize_phone(phone: str) -> str:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 10:
        return "+91" + digits
    return "+" + digits if digits else ""


def _patient(db: Session, phone: str) -> Patient | None:
    if not phone:
        return None
    return db.scalars(select(Patient).where(Patient.phone == _normalize_phone(phone))).first()


class SarvamStartIn(BaseModel):
    from_phone: str | None = None
    call_sid: str | None = None
    conversation_id: str | None = None
    From: str | None = None
    CallSid: str | None = None


class UtteranceIn(BaseModel):
    role: str
    text: str
    lang: str = ""
    ts: datetime | None = None


class SarvamEndIn(BaseModel):
    call_sid: str | None = None
    conversation_id: str | None = None
    outcome: str = "completed"
    utterances: list[UtteranceIn] = []
    from_phone: str | None = None


class TranscriptIn(BaseModel):
    call_sid: str | None = None
    conversation_id: str | None = None
    role: str
    text: str
    lang: str = ""


@router.post("/exotel/status")
async def exotel_status(
    request: Request,
    db: Session = Depends(get_db),
    x_exotel_token: str | None = Header(default=None),
):
    if x_exotel_token and x_exotel_token != settings.exotel_webhook_token:
        raise HTTPException(status_code=401, detail="bad token")
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    else:
        form = await request.form()
        payload = dict(form)
    sid = payload.get("CallSid") or payload.get("call_sid") or payload.get("Sid")
    if not sid:
        raise HTTPException(status_code=400, detail="missing CallSid")
    session = db.scalars(select(CallSession).where(CallSession.exotel_sid == sid)).first()
    if not session:
        session = CallSession(exotel_sid=sid, direction="inbound", agent_name="receptionist")
        db.add(session)
        db.flush()
    session.recording_url = payload.get("RecordingUrl") or payload.get("recording_url") or session.recording_url
    duration = payload.get("DialCallDuration") or payload.get("Duration") or payload.get("duration_sec")
    if duration not in (None, ""):
        session.duration_sec = int(float(duration))
    from_phone = payload.get("From") or payload.get("from_phone")
    if from_phone:
        session.from_phone = _normalize_phone(str(from_phone))
    if payload.get("Status") == "completed" and session.outcome == "in_progress":
        session.outcome = "completed"
    audit(db, "exotel", "status", after={"sid": sid, "keys": list(payload.keys())})
    db.commit()
    return {"ok": True, "call_id": session.id}


@router.post("/sarvam/on-start")
def sarvam_on_start(body: SarvamStartIn, db: Session = Depends(get_db)):
    phone = _normalize_phone(body.from_phone or body.From or "")
    sid = body.call_sid or body.CallSid
    conv = body.conversation_id
    clinic = db.scalars(select(Clinic)).first()
    route = "human" if clinic and clinic.voice_mode == "human" else "bot"
    patient = _patient(db, phone)
    session = None
    if sid:
        session = db.scalars(select(CallSession).where(CallSession.exotel_sid == sid)).first()
    if not session:
        session = CallSession(
            exotel_sid=sid,
            sarvam_conv_id=conv,
            from_phone=phone,
            patient_id=patient.id if patient else None,
            direction="inbound",
            agent_name="receptionist",
            outcome="in_progress",
        )
        db.add(session)
    else:
        session.from_phone = phone or session.from_phone
        session.sarvam_conv_id = conv or session.sarvam_conv_id
        session.patient_id = patient.id if patient else session.patient_id
    if patient:
        db.add(
            Consent(
                patient_id=patient.id,
                purpose="recording",
                channel="voice",
                version="v1",
                granted_at=now_local(),
            )
        )
        db.add(
            Consent(
                patient_id=patient.id,
                purpose="care",
                channel="voice",
                version="v1",
                granted_at=now_local(),
            )
        )
    audit(db, "sarvam", "on_start", after={"sid": sid, "found": bool(patient), "route": route})
    db.commit()
    db.refresh(session)
    if not patient:
        return {
            "route": route,
            "found": False,
            "voice_mode": clinic.voice_mode if clinic else "bot",
            "consent_notice": clinic.consent_notice_gu if clinic else "",
            "call_id": session.id,
        }
    open_appts = []
    for a in open_appointments(db, patient.id):
        open_appts.append(
            {
                "appointment_id": a.id,
                "doctor": a.doctor.display_name,
                "speak_day": speak_day(a.slot_start, patient.language),
                "speak_time": speak_time(a.slot_start, patient.language),
            }
        )
    return {
        "route": route,
        "found": True,
        "patient_id": patient.id,
        "name": patient.name,
        "language": patient.language,
        "open_appts": open_appts,
        "voice_mode": clinic.voice_mode if clinic else "bot",
        "consent_notice": {
            "gu": clinic.consent_notice_gu,
            "hi": clinic.consent_notice_hi,
            "en": clinic.consent_notice_en,
        }.get(patient.language[:2], clinic.consent_notice_en)
        if clinic
        else "",
        "call_id": session.id,
    }


@router.post("/sarvam/on-end")
def sarvam_on_end(body: SarvamEndIn, db: Session = Depends(get_db)):
    session = None
    if body.call_sid:
        session = db.scalars(select(CallSession).where(CallSession.exotel_sid == body.call_sid)).first()
    if not session and body.conversation_id:
        session = db.scalars(
            select(CallSession).where(CallSession.sarvam_conv_id == body.conversation_id)
        ).first()
    if not session:
        session = CallSession(
            exotel_sid=body.call_sid,
            sarvam_conv_id=body.conversation_id,
            from_phone=_normalize_phone(body.from_phone or ""),
            direction="inbound",
        )
        db.add(session)
        db.flush()
    if session.outcome in {"in_progress", ""}:
        session.outcome = body.outcome
    for utt in body.utterances:
        db.add(
            CallUtterance(
                session_id=session.id,
                role=utt.role,
                text=utt.text,
                lang=utt.lang,
                ts=utt.ts or utcnow(),
            )
        )
    audit(db, "sarvam", "on_end", after={"sid": body.call_sid, "outcome": session.outcome})
    db.commit()
    return {"ok": True, "call_id": session.id}


@router.post("/sarvam/transcript")
def sarvam_transcript(body: TranscriptIn, db: Session = Depends(get_db)):
    session = None
    if body.call_sid:
        session = db.scalars(select(CallSession).where(CallSession.exotel_sid == body.call_sid)).first()
    if not session and body.conversation_id:
        session = db.scalars(
            select(CallSession).where(CallSession.sarvam_conv_id == body.conversation_id)
        ).first()
    if not session:
        session = CallSession(
            exotel_sid=body.call_sid,
            sarvam_conv_id=body.conversation_id,
            direction="inbound",
        )
        db.add(session)
        db.flush()
    db.add(
        CallUtterance(
            session_id=session.id,
            role=body.role,
            text=body.text,
            lang=body.lang,
            ts=utcnow(),
        )
    )
    db.commit()
    return {"ok": True}
