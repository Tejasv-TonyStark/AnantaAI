from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.security import create_access_token, verify_password
from app.models import AuditLog, User
from tests.conftest import PASSWORD


@pytest.mark.parametrize("role", [None, "employee", "data_analyst", "security_engineer"])
def test_employee_management_is_admin_only(client, auth_headers, role):
    headers = auth_headers(role) if role else {}
    expected = 403 if role else 401
    data = {"name": "Test", "email": "private@example.com", "password": PASSWORD}
    for path in ["/auth/register", "/admin/users"]:
        assert client.post(path, json=data, headers=headers).status_code == expected
    assert client.patch("/admin/users/1", json={"role": "employee", "is_active": False}, headers=headers).status_code == expected
    assert client.get("/workspace/people", headers=headers).status_code == expected


def test_create_employee_with_role_and_duplicate(client, auth_headers, db):
    headers = auth_headers("admin")
    data = {"name": "New Analyst", "email": "new.analyst@example.com", "password": PASSWORD, "role": "data_analyst"}
    response = client.post("/admin/users", json=data, headers=headers)
    assert response.status_code == 201
    assert response.json()["role"] == "data_analyst"
    assert "password" not in response.text
    user = db.get(User, response.json()["id"])
    assert verify_password(PASSWORD, user.hashed_password)
    assert client.post("/admin/users", json=data, headers=headers).status_code == 409
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "USER_REGISTERED", AuditLog.resource == f"/users/{user.id}"))
    assert db.get(User, audit.user_id).role == "admin"


def test_role_and_status_changes_affect_existing_token(client, auth_headers, db):
    employee_headers = auth_headers("employee")
    admin_headers = auth_headers("admin")
    employee = db.scalar(select(User).where(User.email == "employee@test.example.com"))
    path = f"/admin/users/{employee.id}"
    assert client.post("/agents/sql/query", headers=employee_headers).status_code == 403
    assert client.patch(path, json={"role": "data_analyst", "is_active": True}, headers=admin_headers).status_code == 200
    assert client.post("/agents/sql/query", headers=employee_headers).status_code == 200
    assert client.patch(path, json={"role": "data_analyst", "is_active": False}, headers=admin_headers).status_code == 200
    assert client.get("/users/me", headers=employee_headers).status_code == 401
    assert client.post("/auth/login", json={"email": employee.email, "password": PASSWORD}).status_code == 401
    assert client.patch(path, json={"role": "data_analyst", "is_active": True}, headers=admin_headers).status_code == 200
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.user_id == db.scalar(select(User.id).where(User.email == "admin@test.example.com")))))
    assert {"ROLE_CHANGED", "ACCOUNT_ACTIVATED", "ACCOUNT_DEACTIVATED"} <= actions


def test_admin_protection_and_invalid_update(client, auth_headers, db):
    headers = auth_headers("admin")
    admin = db.scalar(select(User).where(User.email == "admin@test.example.com"))
    for data in [{"role": "employee", "is_active": True}, {"role": "admin", "is_active": False}]:
        assert client.patch(f"/admin/users/{admin.id}", json=data, headers=headers).status_code == 409
    assert client.patch(f"/admin/users/{admin.id}", json={"role": "owner", "is_active": True}, headers=headers).status_code == 422
    assert client.patch("/admin/users/2147483647", json={"role": "employee", "is_active": True}, headers=headers).status_code == 404


def test_change_password_requires_current_password_and_audits(client, auth_headers, db):
    headers = auth_headers("employee")
    path = "/users/me/password"
    assert client.post(path, json={"current_password": "wrong", "new_password": "ChangedPassword123!"}, headers=headers).status_code == 400
    assert client.post(path, json={"current_password": PASSWORD, "new_password": "tiny"}, headers=headers).status_code == 422
    response = client.post(path, json={"current_password": PASSWORD, "new_password": "ChangedPassword123!"}, headers=headers)
    assert response.status_code == 200
    assert client.post("/auth/login", json={"email": "employee@test.example.com", "password": PASSWORD}).status_code == 401
    assert client.post("/auth/login", json={"email": "employee@test.example.com", "password": "ChangedPassword123!"}).status_code == 200
    user = db.scalar(select(User).where(User.email == "employee@test.example.com"))
    assert verify_password("ChangedPassword123!", user.hashed_password)
    logs = db.scalars(select(AuditLog).where(AuditLog.user_id == user.id)).all()
    assert "PASSWORD_CHANGED" in [log.action for log in logs]
    assert all("ChangedPassword123!" not in log.resource for log in logs)


def test_permission_view_and_server_rendered_escape(client, auth_headers, db):
    headers = auth_headers("employee")
    user = db.scalar(select(User).where(User.email == "employee@test.example.com"))
    user.name = '<script>alert("bad")</script>'
    db.commit()
    permissions = client.get("/users/me/permissions", headers=headers).json()
    assert {p["name"] for p in permissions if p["allowed"]} == {"Knowledge hub"}
    response = client.get("/workspace/account", headers=headers)
    assert response.status_code == 200
    assert "&lt;script&gt;" in response.text
    assert '<script>alert' not in response.text
    assert "My permissions" in response.text


def test_activity_filters_and_readable_message(client, auth_headers, db):
    employee = db.scalar(select(User).where(User.email == "data_analyst@test.example.com"))
    employee.name = "Revanth Example"
    db.add(AuditLog(user_id=employee.id, action="AI_AGENT_REQUEST", resource="/agents/sql/query", status="success"))
    db.commit()
    headers = auth_headers("security_engineer")
    today = datetime.now(timezone.utc).date().isoformat()
    params = {"employee_id": employee.id, "search": "Revanth", "start_date": today, "end_date": today}
    rows = client.get("/admin/audit-logs", params=params, headers=headers).json()
    assert rows and all(row["user_id"] == employee.id for row in rows)
    assert any(row["message"] == "Revanth Example opened Data studio (prototype)" for row in rows)
    response = client.get("/workspace/activity", params=params, headers=headers)
    assert response.status_code == 200 and "Revanth Example opened Data studio" in response.text
    assert client.get("/admin/audit-logs", params={"start_date":"2026-02-02", "end_date":"2026-01-01"}, headers=headers).status_code == 422


def test_employee_search_and_role_filter_are_server_side(client, auth_headers):
    headers = auth_headers("admin")
    response = client.get("/admin/users", params={"search":"data_analyst@test", "role":"data_analyst"}, headers=headers)
    assert response.status_code == 200 and len(response.json()) == 1
    assert client.get("/workspace/people", params={"search":"no-matching-person"}, headers=headers).status_code == 200


@pytest.mark.parametrize("path", ["/workspace/account", "/workspace/activity", "/users/me/permissions"])
def test_new_views_require_authentication(client, path):
    assert client.get(path).status_code == 401
