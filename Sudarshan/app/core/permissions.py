from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.services.audit_service import write_audit_log
from app.services.auth_service import get_current_user

ROLE_PERMISSIONS = {
    "employee": {"agent.rag.use"},
    "data_analyst": {"agent.rag.use", "agent.sql.use"},
    "security_engineer": {
        "agent.rag.use", "agent.security.use", "agent.cloud.use", "audit.read"
    },
    "admin": {"*"},
}

ROLE_LABELS = {
    "employee": "Employee", "data_analyst": "Data analyst",
    "security_engineer": "Security engineer", "admin": "Administrator",
}

APPLICATIONS = [
    {"name": "Knowledge hub", "permission": "agent.rag.use", "path": "/agents/rag/chat", "icon": "book-open", "color": "mint", "group": "KNOWLEDGE"},
    {"name": "Data studio", "permission": "agent.sql.use", "path": "/agents/sql/query", "icon": "chart-no-axes-combined", "color": "sky", "group": "ANALYTICS"},
    {"name": "Security desk", "permission": "agent.security.use", "path": "/agents/security/investigate", "icon": "shield-check", "color": "lilac", "group": "SECURITY"},
    {"name": "Cloud operations", "permission": "agent.cloud.use", "path": "/agents/cloud/analyze", "icon": "cloud", "color": "gold", "group": "INFRASTRUCTURE"},
]


def permission_summary(role: str) -> list[dict]:
    resources = [(app["name"], app["permission"]) for app in APPLICATIONS]
    resources += [("Employee management", "users.manage"), ("Activity log", "audit.read")]
    return [{"name": name, "permission": permission, "allowed": has_permission(role, permission),
             "reason": f"{ROLE_LABELS.get(role, role)} role " + ("includes this access." if has_permission(role, permission) else "does not include this access.")}
            for name, permission in resources]


def has_permission(role: str, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(role, set())
    return "*" in permissions or permission in permissions


def require_permission(permission: str):
    def check(
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        allowed = has_permission(user.role, permission)
        write_audit_log(
            db, user.id, "ACCESS_GRANTED" if allowed else "ACCESS_DENIED",
            request.url.path, "granted" if allowed else "denied",
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="Permission denied")
        return user
    return check
