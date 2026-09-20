from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import User

DEMO_USERS = [
    ("Tejasv", "tejasv", "admin", "admin@example.com"),
    ("Gautam Rajavarapu", "gautam.rajavarapu", "employee", "rahul@example.com"),
    ("T Revanth", "t.revanth", "data_analyst", "priya@example.com"),
    ("G Giridar", "g.giridar", "security_engineer", "arjun@example.com"),
    ("Keerthana", "keerthana", "employee", "ananya@example.com"),
    ("Sathvika", "sathvika", "data_analyst", "vikram@example.com"),
    ("Likith", "likith", "security_engineer", "meera@example.com"),
    ("Ranga", "ranga", "employee", "kiran@example.com"),
    ("Vishwa", "vishwa", "security_engineer", None),
    ("Sai", "sai", "employee", None),
    ("Srikar Rao", "srikar.rao", "data_analyst", None),
    ("Nishanth", "nishanth", "employee", None),
    ("SriKar rao", "srikar.rao2", "security_engineer", None),
]


def seed_users(db: Session, password: str) -> None:
    for name, username, role, legacy_email in DEMO_USERS:
        email = f"{username}@sankalpa.example.com"
        if db.scalar(select(User).where(User.email == email)) is not None:
            continue
        # Rename the original demo identities in place, preserving IDs and audit links.
        user = db.scalar(select(User).where(User.email == legacy_email)) if legacy_email else None
        if user is None:
            user = User(hashed_password=hash_password(password))
            db.add(user)
        user.name, user.email, user.role = name, email, role
    db.commit()


def seed() -> None:
    Base.metadata.create_all(engine)
    if not settings.demo_password:
        print("Tables ready; DEMO_PASSWORD is unset, so demo users were not created.")
        return
    with SessionLocal() as db:
        seed_users(db, settings.demo_password.get_secret_value())
    print("Sankalpa employee accounts ready.")


if __name__ == "__main__":
    seed()
