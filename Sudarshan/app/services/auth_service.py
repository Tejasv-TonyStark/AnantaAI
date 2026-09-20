from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.services.audit_service import write_audit_log

bearer = HTTPBearer(auto_error=False)
# Verify a hash for unknown emails too, to reduce account-enumeration timing differences.
DUMMY_HASH = hash_password("unused-dummy-password")


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    valid = verify_password(password, user.hashed_password if user else DUMMY_HASH)
    if not user or not valid or not user.is_active:
        write_audit_log(db, user.id if user else None, "LOGIN_FAILED", "/auth/login", "denied")
        return None
    write_audit_log(db, user.id, "LOGIN_SUCCESS", "/auth/login", "success")
    return user


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    user = None
    if credentials:
        try:
            user = db.get(User, decode_access_token(credentials.credentials))
        except (InvalidTokenError, ValueError, TypeError):
            pass
    if user is None or not user.is_active:
        write_audit_log(db, user.id if user else None, "ACCESS_DENIED", request.url.path, "denied")
        raise HTTPException(
            status_code=401, detail="Invalid or missing credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
