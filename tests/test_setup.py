import re
import pytest
from app.models import Settings, User
from app.routers import setup as _setup_router
from tests.conftest import extract_csrf


def _post_setup(client, **kwargs):
    resp = client.get("/setup/")
    csrf = extract_csrf(resp.text)
    data = {
        "username": "admin",
        "password": "adminpass1",
        "password2": "adminpass1",
        "tag_prefix": "IT",
        "csrf_token": csrf,
        **kwargs,
    }
    return client.post("/setup/", data=data, follow_redirects=False)


# ── middleware guard ──────────────────────────────────────────────────────────

def test_setup_guard_redirects_root(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/setup/" in resp.headers["location"]


def test_setup_guard_redirects_assets(client):
    resp = client.get("/assets/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/setup/" in resp.headers["location"]


def test_setup_static_not_redirected(client):
    resp = client.get("/static/img/logo.svg", follow_redirects=False)
    # 404 is fine — static file may not exist in test env, but it's NOT a 302
    assert resp.status_code != 302


# ── GET /setup/ ───────────────────────────────────────────────────────────────

def test_setup_get_shows_form(client):
    resp = client.get("/setup/")
    assert resp.status_code == 200
    assert "tag_prefix" in resp.text
    assert "csrf_token" in resp.text


def test_setup_not_accessible_after_done(client, db):
    from tests.conftest import make_admin
    make_admin(db)  # sets setup_needed = False
    resp = client.get("/setup/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


# ── POST /setup/ — valid ──────────────────────────────────────────────────────

def test_setup_creates_admin(client, db):
    resp = _post_setup(client, username="myadmin")
    assert resp.status_code == 302
    assert "/login/" in resp.headers["location"]
    user = db.query(User).filter_by(username="myadmin").first()
    assert user is not None
    assert user.is_superuser


def test_setup_saves_tag_prefix(client, db):
    _post_setup(client, tag_prefix="VT")
    setting = db.query(Settings).filter_by(key="tag_prefix").first()
    assert setting is not None
    assert setting.value == "VT"


def test_setup_prefix_lowercased_input_accepted(client, db):
    _post_setup(client, tag_prefix="vt")
    setting = db.query(Settings).filter_by(key="tag_prefix").first()
    assert setting.value == "VT"


def test_setup_clears_setup_needed(client, db):
    _post_setup(client)
    assert _setup_router.setup_needed is False


# ── POST /setup/ — validation ─────────────────────────────────────────────────

def test_setup_missing_username(client):
    resp = _post_setup(client, username="")
    assert resp.status_code == 400
    assert "wymagany" in resp.text


def test_setup_short_password(client):
    resp = _post_setup(client, password="short", password2="short")
    assert resp.status_code == 400
    assert "8 znaków" in resp.text


def test_setup_password_mismatch(client):
    resp = _post_setup(client, password="adminpass1", password2="different1")
    assert resp.status_code == 400
    assert "zgodne" in resp.text


def test_setup_prefix_too_short(client):
    resp = _post_setup(client, tag_prefix="X")
    assert resp.status_code == 400


def test_setup_prefix_with_digits(client):
    resp = _post_setup(client, tag_prefix="1T")
    assert resp.status_code == 400


def test_setup_prefix_too_long(client):
    resp = _post_setup(client, tag_prefix="TOOLONG")
    assert resp.status_code == 400


def test_setup_invalid_csrf(client):
    resp = client.post("/setup/", data={
        "username": "admin", "password": "adminpass1",
        "password2": "adminpass1", "tag_prefix": "IT",
        "csrf_token": "bad",
    })
    assert resp.status_code == 403
