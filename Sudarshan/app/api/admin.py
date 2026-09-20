from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import APPLICATIONS, ROLE_LABELS, require_permission
from app.db.session import get_db
from app.models import AuditLog, User
from app.schemas.user import EmployeeCreate, EmployeeUpdate, RoleName, UserRead
from app.services.employee_service import create_employee

router = APIRouter()


def find_employees(db: Session, search: str = "", role: str | None = None,
                   limit: int = 100, offset: int = 0):
    query = select(User)
    if search:
        query = query.where(or_(User.name.icontains(search, autoescape=True),
                                User.email.icontains(search, autoescape=True)))
    if role:
        query = query.where(User.role == role)
    return db.scalars(query.order_by(User.id).offset(offset).limit(limit)).all()


def describe_event(log: AuditLog, name: str, employee_names: dict[int, str]) -> str:
    resource = next((app["name"] for app in APPLICATIONS if app["path"] == log.resource), log.resource)
    verbs = {
        "LOGIN_SUCCESS": "signed in", "LOGIN_FAILED": "had a failed login",
        "PASSWORD_CHANGED": "changed their password",
        "PASSWORD_CHANGE_FAILED": "had a failed password change",
    }
    if log.action in verbs:
        return f"{name} {verbs[log.action]}"
    if log.action == "AI_AGENT_REQUEST":
        return f"{name} opened {resource} (prototype)"
    if log.action == "ACCESS_DENIED":
        return f"{name} was denied access to {resource}"
    if log.action == "ACCESS_GRANTED":
        return f"{name} was granted access to {resource}"
    parts = log.resource.strip("/").split("/")
    target = employee_names.get(int(parts[1]), f"SK-{parts[1]}") if len(parts) > 1 and parts[1].isdigit() else log.resource
    if log.action == "USER_REGISTERED":
        return f"{name} created an account for {target}"
    if log.action == "ROLE_CHANGED" and len(parts) == 4:
        old, new = parts[3].split("-to-")
        return f"{name} changed {target}'s role from {ROLE_LABELS.get(old, old)} to {ROLE_LABELS.get(new, new)}"
    if log.action in {"ACCOUNT_ACTIVATED", "ACCOUNT_DEACTIVATED"}:
        verb = "activated" if log.action == "ACCOUNT_ACTIVATED" else "deactivated"
        return f"{name} {verb} {target}'s account"
    return f"{name}: {log.action.lower().replace('_', ' ')}"


def find_audit(db: Session, search: str = "", employee_id: int | None = None,
               start_date: date | None = None, end_date: date | None = None,
               limit: int = 100, offset: int = 0):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "Start date must not be after end date")
    query = select(AuditLog, User.name).outerjoin(User, User.id == AuditLog.user_id)
    if employee_id is not None:
        query = query.where(AuditLog.user_id == employee_id)
    if search:
        query = query.where(or_(User.name.icontains(search, autoescape=True),
                                AuditLog.action.icontains(search, autoescape=True),
                                AuditLog.resource.icontains(search, autoescape=True)))
    if start_date:
        query = query.where(AuditLog.timestamp >= datetime.combine(start_date, time.min, timezone.utc))
    if end_date:
        query = query.where(AuditLog.timestamp <= datetime.combine(end_date, time.max, timezone.utc))
    rows = db.execute(query.order_by(AuditLog.id.desc()).offset(offset).limit(limit)).all()
    target_ids = {int(parts[1]) for log, _ in rows
                  if len(parts := log.resource.strip("/").split("/")) > 1 and parts[1].isdigit()}
    employee_names = dict(db.execute(select(User.id, User.name).where(User.id.in_(target_ids))).all()) if target_ids else {}
    return [dict(id=log.id, user_id=log.user_id, employee_name=name or "Unknown employee",
                 action=log.action, resource=log.resource, status=log.status,
                 timestamp=log.timestamp, message=describe_event(log, name or "Unknown employee", employee_names))
            for log, name in rows]


class AuditRead(BaseModel):
    id: int
    user_id: int | None
    employee_name: str
    action: str
    resource: str
    status: str
    timestamp: datetime
    message: str


@router.get("/users", response_model=list[UserRead], dependencies=[Depends(require_permission("users.read"))])
def list_users(search: str = Query("", max_length=100), role: RoleName | None = None,
               limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0),
               db: Session = Depends(get_db)):
    return find_employees(db, search, role, limit, offset)


@router.post("/users", response_model=UserRead, status_code=201)
def add_user(data: EmployeeCreate, actor: User = Depends(require_permission("users.manage")),
             db: Session = Depends(get_db)):
    return create_employee(db, data, actor, data.role)


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(user_id: int, data: EmployeeUpdate,
                actor: User = Depends(require_permission("users.manage")),
                db: Session = Depends(get_db)):
    target = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if target is None:
        raise HTTPException(404, "Employee not found")
    if target.role == "admin" and (data.role != "admin" or not data.is_active):
        raise HTTPException(409, "Administrator accounts cannot be demoted or deactivated here")
    if target.role != data.role:
        db.add(AuditLog(user_id=actor.id, action="ROLE_CHANGED",
                        resource=f"/users/{target.id}/role/{target.role}-to-{data.role}", status="success"))
        target.role = data.role
    if target.is_active != data.is_active:
        db.add(AuditLog(user_id=actor.id, action="ACCOUNT_ACTIVATED" if data.is_active else "ACCOUNT_DEACTIVATED",
                        resource=f"/users/{target.id}", status="success"))
        target.is_active = data.is_active
    db.commit()
    db.refresh(target)
    return target


@router.get("/audit-logs", response_model=list[AuditRead], dependencies=[Depends(require_permission("audit.read"))])
def list_audit_logs(search: str = Query("", max_length=100), employee_id: int | None = Query(None, ge=1),
                    start_date: date | None = None, end_date: date | None = None,
                    limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db)):
    return find_audit(db, search, employee_id, start_date, end_date, limit, offset)
