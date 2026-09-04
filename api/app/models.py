from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.timeutil import utcnow


class VoiceMode(StrEnum):
    bot = "bot"
    human = "human"


class UserRole(StrEnum):
    owner = "owner"
    receptionist = "receptionist"
    doctor = "doctor"
    nurse = "nurse"
    accountant = "accountant"


class AppointmentStatus(StrEnum):
    held = "held"
    booked = "booked"
    confirmed = "confirmed"
    checked_in = "checked_in"
    completed = "completed"
    no_show = "no_show"
    cancelled = "cancelled"


class AppointmentSource(StrEnum):
    voice = "voice"
    web = "web"
    walkin = "walkin"


class ConsentPurpose(StrEnum):
    care = "care"
    reminders = "reminders"
    marketing = "marketing"
    recording = "recording"


class CallDirection(StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class Clinic(Base):
    __tablename__ = "clinics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    voice_mode: Mapped[str] = mapped_column(String(20), default=VoiceMode.bot.value)
    recording_retention_days: Mapped[int] = mapped_column(Integer, default=90)
    consent_notice_gu: Mapped[str] = mapped_column(Text, default="")
    consent_notice_hi: Mapped[str] = mapped_column(Text, default="")
    consent_notice_en: Mapped[str] = mapped_column(Text, default="")

    branches: Mapped[list["Branch"]] = relationship(back_populates="clinic")
    users: Mapped[list["User"]] = relationship(back_populates="clinic")
    patients: Mapped[list["Patient"]] = relationship(back_populates="clinic")


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"))
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100), default="Surat")
    address: Mapped[str] = mapped_column(String(400))
    maps_url: Mapped[str] = mapped_column(String(400), default="")
    phone: Mapped[str] = mapped_column(String(20), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    hours_json: Mapped[dict] = mapped_column(JSON, default=dict)
    after_hours_message: Mapped[str] = mapped_column(Text, default="")

    clinic: Mapped[Clinic] = relationship(back_populates="branches")
    rooms: Mapped[list["Room"]] = relationship(back_populates="branch")
    doctors: Mapped[list["DoctorProfile"]] = relationship(back_populates="branch")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    name: Mapped[str] = mapped_column(String(80))

    branch: Mapped[Branch] = relationship(back_populates="rooms")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(40), default=UserRole.receptionist.value)

    clinic: Mapped[Clinic] = relationship(back_populates="users")
    doctor_profile: Mapped["DoctorProfile | None"] = relationship(back_populates="user")


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    display_name: Mapped[str] = mapped_column(String(200))
    specialties: Mapped[list] = mapped_column(JSON, default=list)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    consult_minutes: Mapped[int] = mapped_column(Integer, default=15)
    fee: Mapped[float] = mapped_column(Float, default=400.0)

    user: Mapped[User] = relationship(back_populates="doctor_profile")
    branch: Mapped[Branch] = relationship(back_populates="doctors")
    schedule_rules: Mapped[list["ScheduleRule"]] = relationship(back_populates="doctor")
    leaves: Mapped[list["Leave"]] = relationship(back_populates="doctor")
    overrides: Mapped[list["Override"]] = relationship(back_populates="doctor")


class ScheduleRule(Base):
    __tablename__ = "schedule_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctor_profiles.id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    weekday: Mapped[int] = mapped_column(Integer)  # 0=Mon
    start_time: Mapped[str] = mapped_column(String(8))  # HH:MM
    end_time: Mapped[str] = mapped_column(String(8))

    doctor: Mapped[DoctorProfile] = relationship(back_populates="schedule_rules")


class Leave(Base):
    __tablename__ = "leaves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctor_profiles.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(String(200), default="")

    doctor: Mapped[DoctorProfile] = relationship(back_populates="leaves")


class Override(Base):
    __tablename__ = "overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctor_profiles.id"))
    date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    start_time: Mapped[str] = mapped_column(String(8), default="")
    end_time: Mapped[str] = mapped_column(String(8), default="")
    closed: Mapped[bool] = mapped_column(Boolean, default=False)

    doctor: Mapped[DoctorProfile] = relationship(back_populates="overrides")


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (UniqueConstraint("clinic_id", "phone"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"))
    phone: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    dob: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(20), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="gu")
    abha_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    clinic: Mapped[Clinic] = relationship(back_populates="patients")
    consents: Mapped[list["Consent"]] = relationship(back_populates="patient")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="patient")


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    purpose: Mapped[str] = mapped_column(String(40))
    channel: Mapped[str] = mapped_column(String(40), default="voice")
    version: Mapped[str] = mapped_column(String(20), default="v1")
    granted_at: Mapped[datetime] = mapped_column(DateTime)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    patient: Mapped[Patient] = relationship(back_populates="consents")


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index(
            "uq_active_doctor_slot",
            "doctor_id",
            "slot_start",
            unique=True,
            sqlite_where=text(
                "status IN ('held','booked','confirmed','checked_in')"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctor_profiles.id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    slot_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    slot_end: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(24), default=AppointmentStatus.booked.value, index=True)
    source: Mapped[str] = mapped_column(String(20), default=AppointmentSource.web.value)
    reason: Mapped[str] = mapped_column(String(400), default="")
    cancel_reason: Mapped[str] = mapped_column(String(400), default="")
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    patient: Mapped[Patient] = relationship(back_populates="appointments")
    doctor: Mapped[DoctorProfile] = relationship()
    visit: Mapped["Visit | None"] = relationship(back_populates="appointment")


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"))
    chief_complaint: Mapped[str] = mapped_column(Text, default="")

    appointment: Mapped[Appointment] = relationship(back_populates="visit")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    amount: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    amount: Mapped[float] = mapped_column(Float, default=0)
    method: Mapped[str] = mapped_column(String(40), default="upi")


class CallSession(Base):
    __tablename__ = "call_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exotel_sid: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    sarvam_conv_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    direction: Mapped[str] = mapped_column(String(20), default=CallDirection.inbound.value)
    agent_name: Mapped[str] = mapped_column(String(80), default="receptionist")
    outcome: Mapped[str] = mapped_column(String(40), default="in_progress")
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    from_phone: Mapped[str] = mapped_column(String(20), default="")
    recording_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transfer_reason: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    utterances: Mapped[list["CallUtterance"]] = relationship(back_populates="session")
    patient: Mapped[Patient | None] = relationship()


class CallUtterance(Base):
    __tablename__ = "call_utterances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("call_sessions.id"))
    role: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    lang: Mapped[str] = mapped_column(String(8), default="")
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    session: Mapped[CallSession] = relationship(back_populates="utterances")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
