from fastapi import APIRouter, Depends, HTTPException
from app.core.permissions import permission_summary
from app.core.security import hash_password, verify_password
from app.models import AuditLog
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import PasswordChange, UserRead
from app.services.audit_service import write_audit_log
from app.services.auth_service import get_current_user

router = APIRouter()


@router.get("/me", response_model=UserRead)
def read_current_user(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> User:
    write_audit_log(db, user.id, "ACCESS_GRANTED", "/users/me", "granted")
    return user


@router.get("/me/permissions")
def my_permissions(user: User = Depends(get_current_user)):
    return permission_summary(user.role)


@router.post("/me/password")
def change_password(data: PasswordChange, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    # Serialize changes so two requests cannot both verify an outdated password.
    user = db.scalar(select(User).where(User.id == user.id).with_for_update()
                     .execution_options(populate_existing=True))
    if not verify_password(data.current_password, user.hashed_password):
        write_audit_log(db, user.id, "PASSWORD_CHANGE_FAILED", "/users/me/password", "denied")
        raise HTTPException(400, "Current password is incorrect")
    if data.current_password == data.new_password:
        raise HTTPException(400, "Choose a different password")
    user.hashed_password = hash_password(data.new_password)
    db.add(AuditLog(user_id=user.id, action="PASSWORD_CHANGED", resource="/users/me/password", status="success"))
    db.commit()
    return {"message": "Password changed. Use your new password next time you sign in."}
