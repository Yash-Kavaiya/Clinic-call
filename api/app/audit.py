from app.timeutil import utcnow

from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(db: Session, actor: str, action: str, before=None, after=None) -> None:
    db.add(
        AuditLog(
            actor=actor,
            action=action,
            before=before,
            after=after,
            created_at=utcnow(),
        )
    )
