import pytest
from app.models import User, UserProfile, Department
from app.auth import verify_password
from tests.conftest import extract_csrf, make_admin, query


def _create_user(auth_client, **overrides):
    resp = auth_client.get("/users/new/")
    csrf = extract_csrf(resp.text)
    data = {
        "first_name": "Jan",
        "last_name": "Kowalski",
        "email": "jan@test.com",
        "csrf_token": csrf,
        **overrides,
    }
    return auth_client.post("/users/new/", data=data, follow_redirects=False)


# ── list ──────────────────────────────────────────────────────────────────────

def test_user_list(auth_client):
    resp = auth_client.get("/users/")
    assert resp.status_code == 200


# ── create ────────────────────────────────────────────────────────────────────

def test_user_create_without_login(auth_client):
    resp = _create_user(auth_client)
    assert resp.status_code == 302
    user = query(User, first_name="Jan", last_name="Kowalski")
    assert user is not None
    assert user.password_hash == ""


def test_user_create_with_login(auth_client):
    resp = _create_user(auth_client,
                        can_login="1",
                        username="jan.kowalski",
                        password1="janpass123",
                        password2="janpass123")
    assert resp.status_code == 302
    user = query(User, username="jan.kowalski")
    assert user is not None
    assert verify_password("janpass123", user.password_hash)


def test_user_create_missing_first_name(auth_client):
    resp = _create_user(auth_client, first_name="")
    assert resp.status_code == 400


def test_user_create_missing_last_name(auth_client):
    resp = _create_user(auth_client, last_name="")
    assert resp.status_code == 400


def test_user_create_duplicate_username(auth_client):
    _create_user(auth_client, can_login="1", username="duplicate",
                 password1="pass1234", password2="pass1234")
    resp = _create_user(auth_client, can_login="1", username="duplicate",
                        password1="pass1234", password2="pass1234",
                        first_name="Anna", last_name="Nowak")
    assert resp.status_code == 400
    assert "zajęty" in resp.text


def test_user_create_password_mismatch(auth_client):
    resp = _create_user(auth_client, can_login="1", username="jan2",
                        password1="pass1234", password2="different")
    assert resp.status_code == 400


def test_user_create_short_password(auth_client):
    resp = _create_user(auth_client, can_login="1", username="jan3",
                        password1="short", password2="short")
    assert resp.status_code == 400


# ── detail ────────────────────────────────────────────────────────────────────

def test_user_detail(auth_client):
    _create_user(auth_client)
    user = query(User, first_name="Jan", last_name="Kowalski")
    resp = auth_client.get(f"/users/{user.id}/")
    assert resp.status_code == 200
    assert "Kowalski" in resp.text


# ── update ────────────────────────────────────────────────────────────────────

def test_user_update(auth_client):
    _create_user(auth_client)
    user = query(User, first_name="Jan", last_name="Kowalski")

    resp = auth_client.get(f"/users/{user.id}/edit/")
    csrf = extract_csrf(resp.text)
    resp = auth_client.post(f"/users/{user.id}/edit/", data={
        "first_name": "Janusz",
        "last_name": "Nowak",
        "email": "janusz@test.com",
        "is_active": "1",
        "csrf_token": csrf,
    }, follow_redirects=False)
    assert resp.status_code == 302

    updated = query(User, id=user.id)
    assert updated.first_name == "Janusz"
    assert updated.last_name == "Nowak"


# ── password change ───────────────────────────────────────────────────────────

def test_admin_can_change_any_password(auth_client):
    _create_user(auth_client, can_login="1", username="target",
                 password1="oldpass1", password2="oldpass1")
    target = query(User, username="target")

    resp = auth_client.get(f"/users/{target.id}/password/")
    csrf = extract_csrf(resp.text)
    resp = auth_client.post(f"/users/{target.id}/password/", data={
        "password1": "newpass123",
        "password2": "newpass123",
        "csrf_token": csrf,
    }, follow_redirects=False)
    assert resp.status_code == 302

    updated = query(User, id=target.id)
    assert verify_password("newpass123", updated.password_hash)


def test_password_change_mismatch(auth_client):
    admin = query(User, username="admin")
    resp = auth_client.get(f"/users/{admin.id}/password/")
    csrf = extract_csrf(resp.text)
    resp = auth_client.post(f"/users/{admin.id}/password/", data={
        "password1": "newpass123",
        "password2": "different1",
        "csrf_token": csrf,
    })
    assert resp.status_code == 400


# ── departments ───────────────────────────────────────────────────────────────

def test_create_department(auth_client):
    resp = auth_client.get("/departments/new/")
    csrf = extract_csrf(resp.text)
    resp = auth_client.post("/departments/new/", data={
        "name": "Nowy Dział",
        "csrf_token": csrf,
    }, follow_redirects=False)
    assert resp.status_code == 302
    dept = query(Department, name="Nowy Dział")
    assert dept is not None


def test_create_department_missing_name(auth_client):
    resp = auth_client.get("/departments/new/")
    csrf = extract_csrf(resp.text)
    resp = auth_client.post("/departments/new/", data={
        "name": "",
        "csrf_token": csrf,
    })
    assert resp.status_code == 400
