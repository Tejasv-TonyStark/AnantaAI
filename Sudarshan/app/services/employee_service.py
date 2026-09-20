from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import AuditLog, User
from app.schemas.user import UserCreate


def create_employee(db: Session, data: UserCreate, actor: User, role: str = "employee") -> User:
    user = User(name=data.name, email=str(data.email), role=role,
                hashed_password=hash_password(data.password))
    try:
        db.add(user)
        db.flush()
        db.add(AuditLog(user_id=actor.id, action="USER_REGISTERED",
                        resource=f"/users/{user.id}", status="success"))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email already registered") from None
    db.refresh(user)
    return user
