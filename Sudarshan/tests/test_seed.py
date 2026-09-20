from sqlalchemy import func, select

from app.db import seed
from app.models import AuditLog, User


def test_company_seed_preserves_identity_and_is_repeatable(db, password_digest, monkeypatch):
    legacy = User(name="Old Demo", email="legacy@test.example.com", role="admin",
                  hashed_password=password_digest)
    db.add(legacy)
    db.flush()
    employee_id = legacy.id
    audit = AuditLog(user_id=employee_id, action="LOGIN_SUCCESS", resource="/auth/login", status="success")
    db.add(audit)
    db.commit()
    monkeypatch.setattr(seed, "DEMO_USERS", [
        ("Company Admin", "seed.admin", "admin", "legacy@test.example.com"),
        ("New Employee", "seed.employee", "employee", None),
    ])
    before = db.scalar(select(func.count()).select_from(User))

    seed.seed_users(db, "NewDemoPassword123!")
    assert legacy.id == employee_id
    assert legacy.name == "Company Admin"
    assert legacy.email == "seed.admin@sankalpa.example.com"
    assert legacy.hashed_password == password_digest
    assert db.get(AuditLog, audit.id).user_id == employee_id
    new_user = db.scalar(select(User).where(User.email == "seed.employee@sankalpa.example.com"))
    assert new_user.hashed_password.startswith("$argon2id$")
    new_user.role = "data_analyst"
    db.commit()

    seed.seed_users(db, "AnotherPassword123!")
    assert db.scalar(select(func.count()).select_from(User)) == before + 1
    assert new_user.role == "data_analyst"
    assert legacy.hashed_password == password_digest
