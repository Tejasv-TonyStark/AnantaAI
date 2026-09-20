from datetime import datetime, timedelta, timezone

import jwt
import pytest
from redis.exceptions import ConnectionError
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, verify_password
from app.models import AuditLog, User
from tests.conftest import PASSWORD


def test_health_and_swagger(client):
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/health").json() == {"status": "healthy", "service": "Sudarshan"}
    assert client.get("/docs").status_code == 200
    assert "/agents/rag/chat" in client.get("/openapi.json").json()["paths"]


def test_login_and_me(client, auth_headers, db):
    headers = auth_headers("employee")
    response = client.get("/users/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["role"] == "employee"
    assert "hashed_password" not in response.text
    token = headers["Authorization"].split()[1]
    payload = jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=["HS256"])
    assert set(payload) == {"sub", "exp"}
    assert decode_access_token(token) == response.json()["id"]
    assert db.scalar(select(AuditLog).where(AuditLog.action == "LOGIN_SUCCESS"))


@pytest.mark.parametrize("email", ["employee@test.example.com", "unknown@test.example.com"])
def test_wrong_credentials(client, db, email):
    response = client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "LOGIN_FAILED"))


def test_missing_token(client):
    response = client.get("/users/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("kind", ["garbage", "expired", "missing_exp", "wrong_signature", "bad_sub", "huge_sub"])
def test_invalid_token(client, kind):
    payload = {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    secret = settings.jwt_secret.get_secret_value()
    if kind == "expired":
        payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    elif kind == "missing_exp":
        del payload["exp"]
    elif kind == "wrong_signature":
        secret = "different-secret-that-is-long-enough"
    elif kind == "bad_sub":
        payload["sub"] = "not-an-id"
    elif kind == "huge_sub":
        payload["sub"] = "9" * 100
    token = "invalid" if kind == "garbage" else jwt.encode(payload, secret, algorithm="HS256")
    assert client.get("/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_unknown_user_token(client):
    token = create_access_token(2147483647)
    assert client.get("/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_inactive_user(client, auth_headers, db):
    headers = auth_headers("employee")
    user = db.scalar(select(User).where(User.role == "employee", User.email.like("%@test.example.com")))
    user.is_active = False
    db.commit()
    assert client.get("/users/me", headers=headers).status_code == 401
    assert client.post("/auth/login", json={"email": user.email, "password": PASSWORD}).status_code == 401


def test_register_hash_duplicate_and_audit(client, db, auth_headers):
    headers = auth_headers("admin")
    data = {"name": " New Employee ", "email": "NEW@example.com", "password": PASSWORD}
    response = client.post("/auth/register", json=data, headers=headers)
    assert response.status_code == 201
    assert response.json()["name"] == "New Employee"
    assert response.json()["role"] == "employee"
    assert "password" not in response.text
    user = db.get(User, response.json()["id"])
    assert user.email == "new@example.com"
    assert user.hashed_password.startswith("$argon2id$")
    assert verify_password(PASSWORD, user.hashed_password)
    assert not verify_password("wrong", user.hashed_password)
    assert client.post("/auth/register", json=data, headers=headers).status_code == 409
    assert db.scalar(select(AuditLog).where(AuditLog.action == "USER_REGISTERED", AuditLog.resource == f"/users/{user.id}"))


@pytest.mark.parametrize("change", [
    {"email": "invalid"}, {"password": "short"}, {"name": " "},
    {"role": "admin"}, {"is_active": True},
])
def test_registration_validation(client, change, auth_headers):
    data = {"name": "Test", "email": "new@example.com", "password": PASSWORD} | change
    response = client.post("/auth/register", json=data, headers=auth_headers("admin"))
    assert response.status_code == 422
    assert PASSWORD not in response.text
    assert "input" not in response.json()["detail"][0]


def test_redis_rate_limit(client, db):
    data = {"email": "employee@test.example.com", "password": "wrong"}
    for _ in range(5):
        assert client.post("/auth/login", json=data).status_code == 401
    response = client.post("/auth/login", json=data)
    assert response.status_code == 429
    assert 1 <= int(response.headers["retry-after"]) <= 60
    assert db.scalar(select(AuditLog).where(AuditLog.status == "rate_limited"))
    key = f"login:{client.test_ip}"
    assert 0 < client.app.state.redis.ttl(key) <= 60
    client.app.state.redis.expire(key, 0)
    assert client.post("/auth/login", json=data).status_code == 401


def test_redis_failure_denies_login(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise ConnectionError("unavailable")
    monkeypatch.setattr(client.app.state.redis, "pipeline", unavailable)
    response = client.post("/auth/login", json={
        "email": "employee@test.example.com", "password": PASSWORD,
    })
    assert response.status_code == 503
