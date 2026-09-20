import pytest
from sqlalchemy import select

from app.models import AuditLog, User

ROUTES = [
    ("POST", "/agents/rag/chat"),
    ("POST", "/agents/sql/query"),
    ("POST", "/agents/security/investigate"),
    ("POST", "/agents/cloud/analyze"),
    ("GET", "/admin/users"),
    ("GET", "/admin/audit-logs"),
]
EXPECTED = {
    "employee": [200, 403, 403, 403, 403, 403],
    "data_analyst": [200, 200, 403, 403, 403, 403],
    "security_engineer": [200, 403, 200, 200, 403, 200],
    "admin": [200, 200, 200, 200, 200, 200],
}


@pytest.mark.parametrize("role", list(EXPECTED))
@pytest.mark.parametrize("index", range(len(ROUTES)))
def test_permission_matrix(client, auth_headers, db, role, index):
    method, path = ROUTES[index]
    response = client.request(method, path, headers=auth_headers(role))
    expected = EXPECTED[role][index]
    assert response.status_code == expected
    assert "hashed_password" not in response.text
    action = "ACCESS_GRANTED" if expected == 200 else "ACCESS_DENIED"
    user = db.scalar(select(User).where(User.email == f"{role}@test.example.com"))
    assert db.scalar(select(AuditLog).where(
        AuditLog.action == action, AuditLog.resource == path, AuditLog.user_id == user.id,
    ))
    agent_log = db.scalar(select(AuditLog).where(
        AuditLog.action == "AI_AGENT_REQUEST", AuditLog.resource == path,
        AuditLog.user_id == user.id,
    ))
    if method == "POST":
        assert bool(agent_log) == (expected == 200)


@pytest.mark.parametrize("method,path", ROUTES)
def test_protected_routes_require_authentication(client, method, path):
    assert client.request(method, path).status_code == 401


def test_permissions_use_current_database_role(client, auth_headers, db):
    headers = auth_headers("admin")
    user = db.scalar(select(User).where(User.email == "admin@test.example.com"))
    user.role = "employee"
    db.commit()
    assert client.get("/admin/users", headers=headers).status_code == 403
