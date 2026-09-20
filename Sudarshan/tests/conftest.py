from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import engine, get_db
from app.main import app
from app.models import User

PASSWORD = "TestPassword123!"


@pytest.fixture(scope="session")
def password_digest():
    return hash_password(PASSWORD)


@pytest.fixture
def db(password_digest):
    # Real PostgreSQL, with application commits contained in an outer rollback.
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        for role in ("employee", "data_analyst", "security_engineer", "admin"):
            session.add(User(
                name=role, email=f"{role}@test.example.com",
                role=role, hashed_password=password_digest,
            ))
        session.commit()
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def client(db):
    def test_db():
        yield db

    app.dependency_overrides[get_db] = test_db
    host = f"pytest-{uuid4().hex}"
    try:
        with TestClient(app, client=(host, 50000)) as test_client:
            test_client.test_ip = host
            try:
                yield test_client
            finally:
                app.state.redis.delete(f"login:{host}")
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    def login(role):
        response = client.post("/auth/login", json={
            "email": f"{role}@test.example.com", "password": PASSWORD,
        })
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    return login
