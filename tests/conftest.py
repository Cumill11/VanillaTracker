import os
import re

# Must be set before any app import so load_dotenv() doesn't override them
os.environ["DATABASE_URL"] = "sqlite:///./test_vanillatracker.db"
os.environ["SECRET_KEY"] = "test-secret-key-32-chars-minimum!!"
os.environ["HTTPS_ONLY"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.database import Base
from app.main import app
from app.models import AssetCounter, Category, Settings, User, UserProfile
from app.auth import hash_password
from app.routers import setup as setup_module
from app.routers.auth import _login_attempts

# Separate engine for tests with NullPool — each session gets a clean connection.
# The app's own engine (app.database.engine) also uses test_vanillatracker.db
# because DATABASE_URL is set above before any app import.
_test_engine = create_engine(
    "sqlite:///./test_vanillatracker.db",
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

_CATEGORIES = [
    ("Laptop", "laptop"), ("Komputer stacjonarny", "desktop"),
    ("Monitor", "monitor"), ("Telefon", "phone"), ("Tablet", "tablet"),
    ("Drukarka", "printer"), ("Sprzęt sieciowy", "network"),
    ("Peryferia", "peripheral"), ("Licencja", "license"), ("Inne", "other"),
]


def _reset_tables():
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    db = TestingSession()
    for name, slug in _CATEGORIES:
        db.add(Category(name=name, slug=slug))
    db.add(AssetCounter(id=1, last_number=0))
    db.commit()
    db.close()


@pytest.fixture(autouse=True)
def reset_db():
    _reset_tables()
    setup_module.setup_needed = True
    _login_attempts.clear()
    yield


@pytest.fixture
def db():
    """Session for test setup and verification.
    Always call db.expire_all() before querying data committed by a route handler,
    to ensure a fresh read from the database file.
    """
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture
def client():
    """Unauthenticated test client. The app uses its own get_db sessions."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def make_admin(db, username="admin", password="admin123"):
    user = User(
        username=username, first_name="Admin", last_name="Test",
        email="admin@test.com",
        password_hash=hash_password(password),
        is_active=True, is_superuser=True,
    )
    db.add(user)
    db.add(Settings(key="tag_prefix", value="IT"))
    db.flush()
    db.add(UserProfile(user_id=user.id))
    db.commit()
    setup_module.setup_needed = False
    return user


@pytest.fixture
def admin_user(db):
    return make_admin(db)


@pytest.fixture
def auth_client(client, admin_user):
    csrf = extract_csrf(client.get("/login/").text)
    client.post("/login/", data={
        "username": "admin",
        "password": "admin123",
        "csrf_token": csrf,
    })
    return client


def extract_csrf(html: str) -> str:
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else ""


def query(model, **filters):
    """Open a fresh session, query, close — guarantees a fresh DB snapshot."""
    session = TestingSession()
    try:
        return session.query(model).filter_by(**filters).first()
    finally:
        session.close()


def query_all(model, **filters):
    session = TestingSession()
    try:
        return session.query(model).filter_by(**filters).all()
    finally:
        session.close()


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    if os.path.exists("test_vanillatracker.db"):
        os.unlink("test_vanillatracker.db")
