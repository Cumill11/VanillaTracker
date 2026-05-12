import pytest
from app.auth import hash_password, verify_password, authenticate
from tests.conftest import make_admin, extract_csrf


def test_hash_and_verify():
    h = hash_password("secret123")
    assert verify_password("secret123", h)


def test_verify_wrong_password():
    h = hash_password("correct")
    assert not verify_password("wrong", h)


def test_hash_unique():
    assert hash_password("same") != hash_password("same")


def test_authenticate_success(db):
    make_admin(db)
    user = authenticate(db, "admin", "admin123")
    assert user is not None
    assert user.username == "admin"


def test_authenticate_wrong_password(db):
    make_admin(db)
    assert authenticate(db, "admin", "badpass") is None


def test_authenticate_unknown_user(db):
    assert authenticate(db, "nobody", "pass") is None


def test_authenticate_inactive_user(db):
    from app.models import User, UserProfile
    user = User(
        username="inactive", password_hash=hash_password("pass"),
        is_active=False, is_superuser=False,
    )
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id))
    db.commit()
    assert authenticate(db, "inactive", "pass") is None


def test_login_page_has_csrf(client, admin_user):
    resp = client.get("/login/")
    assert resp.status_code == 200
    assert 'name="csrf_token"' in resp.text


def test_login_success_redirects(client, admin_user):
    csrf = extract_csrf(client.get("/login/").text)
    resp = client.post("/login/", data={
        "username": "admin",
        "password": "admin123",
        "csrf_token": csrf,
    }, follow_redirects=False)
    assert resp.status_code == 302


def test_login_wrong_credentials(client, admin_user):
    csrf = extract_csrf(client.get("/login/").text)
    resp = client.post("/login/", data={
        "username": "admin",
        "password": "wrong",
        "csrf_token": csrf,
    })
    assert resp.status_code == 400
    assert "Nieprawidłowy" in resp.text


def test_login_invalid_csrf(client, admin_user):
    resp = client.post("/login/", data={
        "username": "admin",
        "password": "admin123",
        "csrf_token": "invalid-token",
    })
    assert resp.status_code == 403


def test_logout(auth_client):
    csrf = extract_csrf(auth_client.get("/").text)
    resp = auth_client.post("/logout/", data={"csrf_token": csrf},
                            follow_redirects=False)
    assert resp.status_code == 302
    assert "/login/" in resp.headers["location"]


def test_unauthenticated_redirects_to_login(client, admin_user):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login/" in resp.headers["location"]
