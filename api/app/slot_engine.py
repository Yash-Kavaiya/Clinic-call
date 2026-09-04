from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    DoctorProfile,
    Leave,
    Override,
    ScheduleRule,
)
from app.speakable import slot_id, speak_day, speak_time

ACTIVE_STATUSES = {
    AppointmentStatus.held.value,
    AppointmentStatus.booked.value,
    AppointmentStatus.confirmed.value,
    AppointmentStatus.checked_in.value,
}

TZ = ZoneInfo(settings.timezone)


def now_local() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


def expire_holds(db: Session, when: datetime | None = None) -> int:
    when = when or now_local()
    rows = db.scalars(
        select(Appointment).where(
            Appointment.status == AppointmentStatus.held.value,
            Appointment.hold_expires_at.is_not(None),
            Appointment.hold_expires_at <= when,
        )
    ).all()
    for row in rows:
        row.status = AppointmentStatus.cancelled.value
        row.cancel_reason = "hold_expired"
    if rows:
        db.flush()
    return len(rows)


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour, minute = value.split(":")
    return int(hour), int(minute)


def _on_leave(leaves: list[Leave], start: datetime, end: datetime) -> bool:
    for leave in leaves:
        if leave.start_at < end and leave.end_at > start:
            return True
    return False


def generate_slots(
    db: Session,
    *,
    doctor: DoctorProfile,
    day: datetime,
    language: str = "en",
    limit: int = 3,
) -> list[dict]:
    expire_holds(db)
    date_s = day.strftime("%Y-%m-%d")
    weekday = day.weekday()
    rules = db.scalars(
        select(ScheduleRule).where(
            ScheduleRule.doctor_id == doctor.id,
            ScheduleRule.weekday == weekday,
        )
    ).all()
    overrides = db.scalars(
        select(Override).where(Override.doctor_id == doctor.id, Override.date == date_s)
    ).all()
    if any(o.closed for o in overrides):
        return []
    if overrides:
        windows = [(o.start_time, o.end_time) for o in overrides if o.start_time and o.end_time]
    else:
        windows = [(r.start_time, r.end_time) for r in rules]
    leaves = db.scalars(select(Leave).where(Leave.doctor_id == doctor.id)).all()
    taken = {
        a.slot_start
        for a in db.scalars(
            select(Appointment).where(
                Appointment.doctor_id == doctor.id,
                Appointment.status.in_(ACTIVE_STATUSES),
                Appointment.slot_start >= datetime(day.year, day.month, day.day),
                Appointment.slot_start < datetime(day.year, day.month, day.day) + timedelta(days=1),
            )
        ).all()
    }
    step = timedelta(minutes=doctor.consult_minutes or 15)
    slots: list[dict] = []
    now = now_local()
    for start_s, end_s in windows:
        sh, sm = _parse_hhmm(start_s)
        eh, em = _parse_hhmm(end_s)
        cursor = datetime(day.year, day.month, day.day, sh, sm)
        end = datetime(day.year, day.month, day.day, eh, em)
        while cursor + step <= end:
            slot_end = cursor + step
            if cursor >= now and cursor not in taken and not _on_leave(leaves, cursor, slot_end):
                slots.append(
                    {
                        "slot_id": slot_id(doctor.id, cursor),
                        "doctor_id": doctor.id,
                        "doctor_name": doctor.display_name,
                        "slot_start": cursor.isoformat(timespec="minutes"),
                        "slot_end": slot_end.isoformat(timespec="minutes"),
                        "speak_time": speak_time(cursor, language),
                        "speak_day": speak_day(cursor, language),
                    }
                )
                if len(slots) >= limit:
                    return slots
            cursor += step
    return slots


def availability(
    db: Session,
    *,
    date_s: str,
    doctor_id: int | None = None,
    specialty: str | None = None,
    branch_id: int | None = None,
    language: str = "en",
    limit: int = 3,
) -> list[dict]:
    day = datetime.strptime(date_s, "%Y-%m-%d")
    q = select(DoctorProfile)
    if doctor_id:
        q = q.where(DoctorProfile.id == doctor_id)
    if branch_id:
        q = q.where(DoctorProfile.branch_id == branch_id)
    doctors = db.scalars(q).all()
    if specialty:
        spec = specialty.lower()
        doctors = [
            d
            for d in doctors
            if any(spec in str(s).lower() for s in (d.specialties or []))
        ]
    out: list[dict] = []
    for doctor in doctors:
        remaining = limit - len(out)
        if remaining <= 0:
            break
        out.extend(generate_slots(db, doctor=doctor, day=day, language=language, limit=remaining))
    return out[:limit]


def slot_is_offered(
    db: Session,
    *,
    doctor_id: int,
    slot_start: datetime,
    language: str = "en",
) -> bool:
    doctor = db.get(DoctorProfile, doctor_id)
    if not doctor:
        return False
    offered = generate_slots(db, doctor=doctor, day=slot_start, language=language, limit=32)
    wanted = slot_id(doctor_id, slot_start)
    return any(s["slot_id"] == wanted for s in offered)


def hold_slot(
    db: Session,
    *,
    patient_id: int,
    doctor_id: int,
    slot_start: datetime,
    reason: str = "",
    source: str = AppointmentSource.voice.value,
) -> Appointment:
    expire_holds(db)
    doctor = db.get(DoctorProfile, doctor_id)
    if not doctor:
        raise ValueError("unknown_doctor")
    if not slot_is_offered(db, doctor_id=doctor_id, slot_start=slot_start):
        raise ValueError("slot_not_available")
    end = slot_start + timedelta(minutes=doctor.consult_minutes or 15)
    appt = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        branch_id=doctor.branch_id,
        slot_start=slot_start,
        slot_end=end,
        status=AppointmentStatus.held.value,
        source=source,
        reason=reason,
        hold_expires_at=now_local() + timedelta(seconds=settings.hold_seconds),
    )
    db.add(appt)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("slot_taken") from exc
    return appt


def book_appointment(
    db: Session,
    *,
    patient_id: int,
    doctor_id: int,
    slot_start: datetime,
    reason: str = "",
    source: str = AppointmentSource.voice.value,
    hold_id: int | None = None,
) -> Appointment:
    expire_holds(db)
    doctor = db.get(DoctorProfile, doctor_id)
    if not doctor:
        raise ValueError("unknown_doctor")
    if hold_id:
        appt = db.get(Appointment, hold_id)
        if (
            not appt
            or appt.status != AppointmentStatus.held.value
            or appt.doctor_id != doctor_id
            or appt.slot_start != slot_start
            or appt.patient_id != patient_id
        ):
            raise ValueError("hold_invalid")
        if appt.hold_expires_at and appt.hold_expires_at < now_local():
            raise ValueError("hold_expired")
        appt.status = AppointmentStatus.booked.value
        appt.reason = reason or appt.reason
        appt.hold_expires_at = None
        db.flush()
        return appt
    if not slot_is_offered(db, doctor_id=doctor_id, slot_start=slot_start):
        raise ValueError("slot_not_available")
    end = slot_start + timedelta(minutes=doctor.consult_minutes or 15)
    appt = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        branch_id=doctor.branch_id,
        slot_start=slot_start,
        slot_end=end,
        status=AppointmentStatus.booked.value,
        source=source,
        reason=reason,
    )
    db.add(appt)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("slot_taken") from exc
    return appt


def cancel_appointment(db: Session, appointment_id: int, reason: str = "") -> Appointment:
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise ValueError("not_found")
    if appt.status in {AppointmentStatus.cancelled.value, AppointmentStatus.completed.value}:
        raise ValueError("not_cancellable")
    appt.status = AppointmentStatus.cancelled.value
    appt.cancel_reason = reason
    db.flush()
    return appt


def set_status(db: Session, appointment_id: int, status: str) -> Appointment:
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise ValueError("not_found")
    appt.status = status
    db.flush()
    return appt


def open_appointments(db: Session, patient_id: int) -> list[Appointment]:
    expire_holds(db)
    return list(
        db.scalars(
            select(Appointment)
            .options(joinedload(Appointment.doctor))
            .where(
                Appointment.patient_id == patient_id,
                Appointment.status.in_(
                    [
                        AppointmentStatus.held.value,
                        AppointmentStatus.booked.value,
                        AppointmentStatus.confirmed.value,
                        AppointmentStatus.checked_in.value,
                    ]
                ),
            )
            .order_by(Appointment.slot_start)
        ).unique()
    )
