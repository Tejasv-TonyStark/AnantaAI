from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def write_audit_log(
    db: Session, user_id: int | None, action: str, resource: str, status: str
) -> None:
    db.add(AuditLog(
        user_id=user_id, action=action, resource=resource, status=status
    ))
    db.commit()
