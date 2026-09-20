from fastapi import APIRouter, Depends, HTTPException, Request
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import require_permission
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.audit_service import write_audit_log
from app.services.auth_service import authenticate_user
from app.services.employee_service import create_employee

router = APIRouter()


def limit_login(request: Request, db: Session = Depends(get_db)) -> None:
    ip = request.client.host if request.client else "unknown"
    key = f"login:{ip}"
    try:
        # Atomic counter + expiry; NX anchors the window to the first attempt.
        with request.app.state.redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, 60, nx=True)
            pipe.ttl(key)
            count, _, ttl = pipe.execute()
    except RedisError:
        raise HTTPException(status_code=503, detail="Login temporarily unavailable") from None
    if count > settings.login_rate_limit:
        write_audit_log(db, None, "LOGIN_FAILED", "/auth/login", "rate_limited")
        raise HTTPException(
            status_code=429, detail="Too Many Requests",
            headers={"Retry-After": str(max(ttl, 1))},
        )


@router.post("/register", response_model=UserRead, status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db),
             actor: User = Depends(require_permission("users.manage"))) -> User:
    return create_employee(db, data, actor)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(limit_login)])
def login(data: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, str(data.email), data.password)
    if user is None:
        raise HTTPException(
            status_code=401, detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.id))
