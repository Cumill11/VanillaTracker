import pytest
from app.models import License, User, UserProfile
from app.auth import hash_password
from tests.conftest import extract_csrf, query, TestingSession


def _create_license(auth_client, **overrides):
    resp = auth_client.get("/licenses/new/")
    csrf = extract_csrf(resp.text)
    data = {
        "name": "Test License",
        "vendor": "Microsoft",
        "seats": "5",
        "status": "active",
        "csrf_token": csrf,
        **overrides,
    }
    return auth_client.post("/licenses/new/", data=data, follow_redirects=False)


# ── list ──────────────────────────────────────────────────────────────────────

def test_license_list(auth_client):
    resp = auth_client.get("/licenses/")
    assert resp.status_code == 200


# ── create ────────────────────────────────────────────────────────────────────

def test_license_create_success(auth_client):
    resp = _create_license(auth_client)
    assert resp.status_code == 302
    lic = query(License, name="Test License")
    assert lic is not None
    assert lic.seats == 5


def test_license_create_uses_tag_prefix(auth_client):
    _create_license(auth_client)
    lic = query(License, name="Test License")
    assert lic.asset_tag.startswith("IT-")


def test_license_create_missing_name(auth_client):
    resp = _create_license(auth_client, name="")
    assert resp.status_code == 400


def test_license_create_invalid_seats_defaults_to_1(auth_client):
    _create_license(auth_client, seats="abc")
    lic = query(License, name="Test License")
    assert lic.seats == 1


# ── detail ────────────────────────────────────────────────────────────────────

def test_license_detail(auth_client):
    _create_license(auth_client)
    lic = query(License, name="Test License")
    resp = auth_client.get(f"/licenses/{lic.id}/")
    assert resp.status_code == 200
    assert "Test License" in resp.text


# ── update ────────────────────────────────────────────────────────────────────

def test_license_update(auth_client):
    _create_license(auth_client)
    lic = query(License, name="Test License")

    resp = auth_client.get(f"/licenses/{lic.id}/edit/")
    csrf = extract_csrf(resp.text)
    resp = auth_client.post(f"/licenses/{lic.id}/edit/", data={
        "name": "Updated License",
        "vendor": "Adobe",
        "seats": "10",
        "status": "inactive",
        "csrf_token": csrf,
    }, follow_redirects=False)
    assert resp.status_code == 302

    updated = query(License, id=lic.id)
    assert updated.name == "Updated License"
    assert updated.seats == 10
    assert updated.status == "inactive"


# ── delete ────────────────────────────────────────────────────────────────────

def test_license_delete(auth_client):
    _create_license(auth_client)
    lic = query(License, name="Test License")
    lic_id = lic.id

    resp = auth_client.get(f"/licenses/{lic_id}/delete/")
    csrf = extract_csrf(resp.text)
    resp = auth_client.post(f"/licenses/{lic_id}/delete/",
                            data={"csrf_token": csrf},
                            follow_redirects=False)
    assert resp.status_code == 302
    assert query(License, id=lic_id) is None


# ── assign users ──────────────────────────────────────────────────────────────

def test_license_assign_users(auth_client, db):
    _create_license(auth_client)
    lic = query(License, name="Test License")
    lic_id = lic.id

    worker = User(username="worker", password_hash=hash_password("pass"),
                  is_active=True, is_superuser=False)
    db.add(worker)
    db.flush()
    db.add(UserProfile(user_id=worker.id))
    db.commit()
    worker_id = worker.id

    csrf = extract_csrf(auth_client.get(f"/licenses/{lic_id}/").text)
    resp = auth_client.post(f"/licenses/{lic_id}/assign/", data={
        "users": str(worker_id),
        "csrf_token": csrf,
    }, follow_redirects=False)
    assert resp.status_code == 302

    with TestingSession() as fresh_db:
        updated_lic = fresh_db.query(License).filter_by(id=lic_id).first()
        assert any(u.id == worker_id for u in updated_lic.assigned_users)


def test_license_assign_invalid_user_ids(auth_client):
    _create_license(auth_client)
    lic = query(License, name="Test License")
    lic_id = lic.id
    csrf = extract_csrf(auth_client.get(f"/licenses/{lic_id}/").text)
    resp = auth_client.post(f"/licenses/{lic_id}/assign/", data={
        "users": "not-a-number",
        "csrf_token": csrf,
    }, follow_redirects=False)
    assert resp.status_code == 302
    with TestingSession() as fresh_db:
        updated_lic = fresh_db.query(License).filter_by(id=lic_id).first()
        assert updated_lic.assigned_users == []
