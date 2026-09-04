from app.timeutil import utcnow

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import settings
from app.models import (
    Branch,
    Clinic,
    DoctorProfile,
    Patient,
    Room,
    ScheduleRule,
    User,
    UserRole,
)

NOTICE_GU = (
    "Call record thai shake, appointment ane mahiti mate. "
    "90 divas sudhi rakhiye. Appointment mate 1, receptionist mate 0."
)
NOTICE_HI = (
    "Yeh call record ho sakti hai, appointment ke liye. "
    "90 din tak rakhenge. Appointment ke liye 1, receptionist ke liye 0."
)
NOTICE_EN = (
    "This call may be recorded for appointments. "
    "We keep recordings 90 days. Press 1 to continue, 0 for a receptionist."
)

HOURS = {
    "mon": [["09:00", "13:00"], ["17:00", "20:00"]],
    "tue": [["09:00", "13:00"], ["17:00", "20:00"]],
    "wed": [["09:00", "13:00"], ["17:00", "20:00"]],
    "thu": [["09:00", "13:00"], ["17:00", "20:00"]],
    "fri": [["09:00", "13:00"], ["17:00", "20:00"]],
    "sat": [["09:00", "13:00"]],
    "sun": [],
}


def seed_if_empty(db: Session) -> None:
    if db.query(Clinic).first():
        return
    clinic = Clinic(
        name="Adajan Family Clinic",
        voice_mode="bot",
        recording_retention_days=90,
        consent_notice_gu=NOTICE_GU,
        consent_notice_hi=NOTICE_HI,
        consent_notice_en=NOTICE_EN,
    )
    db.add(clinic)
    db.flush()
    branch = Branch(
        clinic_id=clinic.id,
        name="Adajan",
        city="Surat",
        address="VIP Road, Adajan, Surat, Gujarat",
        maps_url="https://maps.google.com/?q=Adajan+Surat",
        phone="+912612345678",
        timezone=settings.timezone,
        hours_json=HOURS,
        after_hours_message=(
            "Clinic bandh chhe. Emergency hoy to 108 ke nearest hospital. "
            "Aapde diagnosis nathi aapta."
        ),
    )
    db.add(branch)
    db.flush()
    db.add(Room(branch_id=branch.id, name="OPD 1"))
    db.add(Room(branch_id=branch.id, name="OPD 2"))
    reception = User(
        clinic_id=clinic.id,
        email=settings.seed_reception_email,
        password_hash=hash_password(settings.seed_reception_password),
        name="Front Desk",
        role=UserRole.receptionist.value,
    )
    db.add(reception)
    meera_user = User(
        clinic_id=clinic.id,
        email="meera.shah@adajan.clinic",
        password_hash=hash_password("unused"),
        name="Dr. Meera Shah",
        role=UserRole.doctor.value,
    )
    rohan_user = User(
        clinic_id=clinic.id,
        email="rohan.patel@adajan.clinic",
        password_hash=hash_password("unused"),
        name="Dr. Rohan Patel",
        role=UserRole.doctor.value,
    )
    db.add_all([meera_user, rohan_user])
    db.flush()
    meera = DoctorProfile(
        user_id=meera_user.id,
        branch_id=branch.id,
        display_name="Dr. Meera Shah",
        specialties=["gp", "general"],
        languages=["gu", "hi", "en"],
        consult_minutes=15,
        fee=400,
    )
    rohan = DoctorProfile(
        user_id=rohan_user.id,
        branch_id=branch.id,
        display_name="Dr. Rohan Patel",
        specialties=["dental", "dentist"],
        languages=["gu", "hi", "en"],
        consult_minutes=20,
        fee=600,
    )
    db.add_all([meera, rohan])
    db.flush()
    for weekday in range(6):  # Mon-Sat
        morning_end = "13:00" if weekday < 5 else "13:00"
        db.add(
            ScheduleRule(
                doctor_id=meera.id,
                branch_id=branch.id,
                weekday=weekday,
                start_time="09:00",
                end_time=morning_end,
            )
        )
        if weekday < 5:
            db.add(
                ScheduleRule(
                    doctor_id=meera.id,
                    branch_id=branch.id,
                    weekday=weekday,
                    start_time="17:00",
                    end_time="20:00",
                )
            )
            db.add(
                ScheduleRule(
                    doctor_id=rohan.id,
                    branch_id=branch.id,
                    weekday=weekday,
                    start_time="17:00",
                    end_time="20:00",
                )
            )
        db.add(
            ScheduleRule(
                doctor_id=rohan.id,
                branch_id=branch.id,
                weekday=weekday,
                start_time="09:30",
                end_time="13:00",
            )
        )
    db.add_all(
        [
            Patient(
                clinic_id=clinic.id,
                phone="+919876543210",
                name="Kiran Desai",
                language="gu",
                dob="1988-04-12",
                sex="F",
            ),
            Patient(
                clinic_id=clinic.id,
                phone="+919123456789",
                name="Amit Shah",
                language="hi",
                dob="1975-11-02",
                sex="M",
            ),
        ]
    )
    db.commit()


def iso_now() -> str:
    return utcnow().isoformat()
