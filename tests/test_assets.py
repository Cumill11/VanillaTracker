import pytest
from app.models import Asset, AssetHistory, Category, User, UserProfile
from app.auth import hash_password
from tests.conftest import extract_csrf, query, query_all, TestingSession


def _cat_id(db, slug="laptop"):
    return db.query(Category).filter_by(slug=slug).first().id


def _create_asset(auth_client, db, **overrides):
    cat_id = _cat_id(db)
    resp = auth_client.get("/assets/new/")
    csrf = extract_csrf(resp.text)
    data = {
        "name": "Test Laptop",
        "category_id": str(cat_id),
        "manufacturer": "Dell",
        "model_name": "Test Model",
        "status": "available",
        "csrf_token": csrf,
        **overrides,
    }
    return auth_client.post("/assets/new/", data=data, follow_redirects=False)


# ── list ──────────────────────────────────────────────────────────────────────

def test_asset_list_empty(auth_client):
    resp = auth_client.get("/assets/")
    assert resp.status_code == 200


def test_asset_list_unauthenticated(client, admin_user):
    resp = client.get("/assets/", follow_redirects=False)
    assert resp.status_code == 302


# ── create ────────────────────────────────────────────────────────────────────

def test_asset_create_success(auth_client, db):
    resp = _create_asset(auth_client, db)
    assert resp.status_code == 302
    assert query(Asset, name="Test Laptop") is not None


def test_asset_create_uses_tag_prefix(auth_client, db):
    _create_asset(auth_client, db)
    asset = query(Asset, name="Test Laptop")
    assert asset.asset_tag.startswith("IT-")


def test_asset_create_increments_counter(auth_client, db):
    _create_asset(auth_client, db, name="Asset A")
    _create_asset(auth_client, db, name="Asset B")
    a = query(Asset, name="Asset A")
    b = query(Asset, name="Asset B")
    assert b.tag_number == a.tag_number + 1


def test_asset_create_adds_history(auth_client, db):
    _create_asset(auth_client, db)
    asset = query(Asset, name="Test Laptop")
    history = query_all(AssetHistory, asset_id=asset.id)
    assert len(history) >= 1


def test_asset_create_missing_name(auth_client, db):
    resp = _create_asset(auth_client, db, name="")
    assert resp.status_code == 400


def test_asset_create_missing_manufacturer(auth_client, db):
    resp = _create_asset(auth_client, db, manufacturer="")
    assert resp.status_code == 400


def test_asset_create_invalid_category(auth_client, db):
    resp = _create_asset(auth_client, db, category_id="abc")
    assert resp.status_code == 400


# ── detail ────────────────────────────────────────────────────────────────────

def test_asset_detail(auth_client, db):
    _create_asset(auth_client, db)
    asset = query(Asset, name="Test Laptop")
    resp = auth_client.get(f"/assets/{asset.id}/")
    assert resp.status_code == 200
    assert "Test Laptop" in resp.text


def test_asset_detail_not_found(auth_client):
    resp = auth_client.get("/assets/99999/", follow_redirects=False)
    assert resp.status_code == 302


# ── update ────────────────────────────────────────────────────────────────────

def test_asset_update(auth_client, db):
    _create_asset(auth_client, db)
    asset = query(Asset, name="Test Laptop")
    cat_id = _cat_id(db, "monitor")

    resp = auth_client.get(f"/assets/{asset.id}/edit/")
    csrf = extract_csrf(resp.text)
    resp = auth_client.post(f"/assets/{asset.id}/edit/", data={
        "name": "Updated Name",
        "category_id": str(cat_id),
        "manufacturer": "HP",
        "model_name": "New Model",
        "status": "maintenance",
        "csrf_token": csrf,
    }, follow_redirects=False)
    assert resp.status_code == 302

    updated = query(Asset, id=asset.id)
    assert updated.name == "Updated Name"
    assert updated.status == "maintenance"


# ── delete ────────────────────────────────────────────────────────────────────

def test_asset_delete(auth_client, db):
    _create_asset(auth_client, db)
    asset = query(Asset, name="Test Laptop")
    asset_id = asset.id

    resp = auth_client.get(f"/assets/{asset_id}/delete/")
    csrf = extract_csrf(resp.text)
    resp = auth_client.post(f"/assets/{asset_id}/delete/",
                            data={"csrf_token": csrf},
                            follow_redirects=False)
    assert resp.status_code == 302
    assert query(Asset, id=asset_id) is None


# ── assign / return ───────────────────────────────────────────────────────────

def _make_user(db, username="worker"):
    u = User(username=username, password_hash=hash_password("pass"),
             is_active=True, is_superuser=False)
    db.add(u)
    db.flush()
    db.add(UserProfile(user_id=u.id))
    db.commit()
    return u


def test_asset_assign(auth_client, db):
    _create_asset(auth_client, db)
    asset = query(Asset, name="Test Laptop")
    worker = _make_user(db)

    csrf = extract_csrf(auth_client.get(f"/assets/{asset.id}/").text)
    resp = auth_client.post(f"/assets/{asset.id}/assign/", data={
        "assign_user_id": str(worker.id),
        "assigned_date": "2024-01-01",
        "csrf_token": csrf,
    }, follow_redirects=False)
    assert resp.status_code == 302

    updated = query(Asset, id=asset.id)
    assert updated.assigned_to_id == worker.id
    assert updated.status == "assigned"


def test_asset_return(auth_client, db):
    _create_asset(auth_client, db)
    asset = query(Asset, name="Test Laptop")
    worker = _make_user(db)

    csrf = extract_csrf(auth_client.get(f"/assets/{asset.id}/").text)
    auth_client.post(f"/assets/{asset.id}/assign/", data={
        "assign_user_id": str(worker.id),
        "assigned_date": "2024-01-01",
        "csrf_token": csrf,
    })

    csrf = extract_csrf(auth_client.get(f"/assets/{asset.id}/").text)
    resp = auth_client.post(f"/assets/{asset.id}/return/",
                            data={"csrf_token": csrf},
                            follow_redirects=False)
    assert resp.status_code == 302

    updated = query(Asset, id=asset.id)
    assert updated.assigned_to_id is None
    assert updated.status == "available"


# ── assign — invalid user id ──────────────────────────────────────────────────

def test_asset_assign_invalid_user_id(auth_client, db):
    _create_asset(auth_client, db)
    asset = query(Asset, name="Test Laptop")
    csrf = extract_csrf(auth_client.get(f"/assets/{asset.id}/").text)
    resp = auth_client.post(f"/assets/{asset.id}/assign/", data={
        "assign_user_id": "not-a-number",
        "csrf_token": csrf,
    }, follow_redirects=False)
    assert resp.status_code == 302
    updated = query(Asset, id=asset.id)
    assert updated.assigned_to_id is None
