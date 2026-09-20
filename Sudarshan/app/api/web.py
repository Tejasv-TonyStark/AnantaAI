from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.admin import find_audit, find_employees
from app.core.permissions import APPLICATIONS, ROLE_LABELS, permission_summary, require_permission
from app.db.seed import DEMO_USERS
from app.db.session import get_db
from app.models import User
from app.schemas.user import RoleName
from app.services.auth_service import get_current_user

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
templates.env.globals.update(roles=ROLE_LABELS, company="Sankalpa.AI")


def render(request: Request, name: str, **context):
    response = templates.TemplateResponse(request=request, name=name, context=context)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/")
def home(request: Request):
    return render(request, "index.html", applications=APPLICATIONS, demo_employees=DEMO_USERS)


@router.get("/workspace/people", dependencies=[Depends(require_permission("users.read"))])
def people(request: Request, search: str = Query("", max_length=100), role: RoleName | None = None,
           offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    rows = find_employees(db, search, role, 25, offset)
    return render(request, "people.html", rows=rows, offset=offset)


@router.get("/workspace/activity", dependencies=[Depends(require_permission("audit.read"))])
def activity(request: Request, search: str = Query("", max_length=100),
             employee_id: int | None = Query(None, ge=1), start_date: date | None = None,
             end_date: date | None = None, offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    rows = find_audit(db, search, employee_id, start_date, end_date, 25, offset)
    return render(request, "activity.html", rows=rows, offset=offset)


@router.get("/workspace/account")
def account(request: Request, user: User = Depends(get_current_user)):
    return render(request, "account.html", user=user, permissions=permission_summary(user.role))
