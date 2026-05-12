from datetime import date as parse_date
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import verify_csrf
from app.deps import ctx, login_required
from app.flash import add_message
from app.models import Asset, AssetCounter, AssetHistory, License, Settings, User
from app.pagination import paginate

router = APIRouter(prefix="/licenses")
templates: Jinja2Templates = None


def _next_tag(db: Session) -> tuple[int, str]:
    s = db.query(Settings).filter_by(key="tag_prefix").first()
    prefix = s.value if s else "BS"
    counter = db.query(AssetCounter).filter_by(id=1).with_for_update().first()
    if counter is None:
        counter = AssetCounter(id=1, last_number=0)
        db.add(counter)
        db.flush()
    counter.last_number += 1
    db.flush()
    return counter.last_number, f"{prefix}-{counter.last_number:05d}"


def _parse_date(s: str):
    if not s:
        return None
    try:
        return parse_date.fromisoformat(s)
    except ValueError:
        return None


def _parse_decimal(s: str):
    if not s:
        return None
    try:
        return Decimal(s.replace(",", "."))
    except InvalidOperation:
        return None


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/", name="license-list")
async def license_list(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    q: str = "",
    status: str = "",
    page: int = 1,
):
    base = ctx(request, db)
    qs = db.query(License)
    if q:
        qs = qs.filter(or_(
            License.asset_tag.ilike(f"%{q}%"),
            License.name.ilike(f"%{q}%"),
            License.vendor.ilike(f"%{q}%"),
        ))
    if status:
        qs = qs.filter(License.status == status)
    qs = qs.order_by(License.tag_number)
    pagination = paginate(qs, page)
    return templates.TemplateResponse("license_list.html", {
        **base,
        "licenses": pagination.items,
        "pagination": pagination,
        "status_choices": License.STATUS_CHOICES,
        "current_q": q,
        "current_status": status,
    })


# ── Create ────────────────────────────────────────────────────────────────────

@router.get("/new/", name="license-create")
async def license_create_get(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    base = ctx(request, db)
    return templates.TemplateResponse("license_form.html", {
        **base,
        "title": "Dodaj licencję",
        "status_choices": License.STATUS_CHOICES,
        "errors": {}, "form_data": {},
    })


@router.post("/new/", name="license-create-post")
async def license_create_post(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    name: str = Form(""),
    vendor: str = Form(""),
    license_key: str = Form(""),
    seats: str = Form("1"),
    purchase_date: str = Form(""),
    expiry_date: str = Form(""),
    purchase_price: str = Form(""),
    status: str = Form("active"),
    notes: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    base = ctx(request, db)
    errors = {}
    if not name.strip():
        errors["name"] = ["To pole jest wymagane."]
    if errors:
        form_data = dict(name=name, vendor=vendor, license_key=license_key, seats=seats,
                         purchase_date=purchase_date, expiry_date=expiry_date,
                         purchase_price=purchase_price, status=status, notes=notes)
        return templates.TemplateResponse("license_form.html", {
            **base, "title": "Dodaj licencję",
            "status_choices": License.STATUS_CHOICES,
            "errors": errors, "form_data": form_data,
        }, status_code=400)

    num, tag = _next_tag(db)
    lic = License(
        asset_tag=tag, tag_number=num,
        name=name.strip(), vendor=vendor.strip(), license_key=license_key.strip(),
        seats=int(seats) if seats.isdigit() else 1,
        purchase_date=_parse_date(purchase_date),
        expiry_date=_parse_date(expiry_date),
        purchase_price=_parse_decimal(purchase_price),
        status=status, notes=notes.strip(),
    )
    db.add(lic)
    db.commit()
    add_message(request, f"Licencja {lic.asset_tag} dodana.")
    return RedirectResponse(f"/licenses/{lic.id}/", status_code=302)


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{pk}/", name="license-detail")
async def license_detail(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    lic = db.query(License).filter_by(id=pk).first()
    if not lic:
        return RedirectResponse("/licenses/", status_code=302)
    base = ctx(request, db)
    history = (
        db.query(AssetHistory)
        .filter_by(license_id=pk)
        .order_by(AssetHistory.created_at.desc())
        .all()
    )
    all_users = db.query(User).filter_by(is_active=True).order_by(User.last_name, User.first_name).all()
    assigned_ids = {u.id for u in lic.assigned_users}
    return templates.TemplateResponse("license_detail.html", {
        **base,
        "license": lic,
        "history": history,
        "all_users": all_users,
        "assigned_ids": assigned_ids,
    })


# ── Update ────────────────────────────────────────────────────────────────────

@router.get("/{pk}/edit/", name="license-update")
async def license_update_get(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    lic = db.query(License).filter_by(id=pk).first()
    if not lic:
        return RedirectResponse("/licenses/", status_code=302)
    base = ctx(request, db)
    form_data = {
        "name": lic.name, "vendor": lic.vendor, "license_key": lic.license_key,
        "seats": str(lic.seats),
        "purchase_date": lic.purchase_date.isoformat() if lic.purchase_date else "",
        "expiry_date": lic.expiry_date.isoformat() if lic.expiry_date else "",
        "purchase_price": str(lic.purchase_price) if lic.purchase_price else "",
        "status": lic.status, "notes": lic.notes,
    }
    return templates.TemplateResponse("license_form.html", {
        **base,
        "title": f"Edytuj {lic.asset_tag}",
        "object": lic,
        "status_choices": License.STATUS_CHOICES,
        "errors": {}, "form_data": form_data,
    })


@router.post("/{pk}/edit/", name="license-update-post")
async def license_update_post(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    name: str = Form(""),
    vendor: str = Form(""),
    license_key: str = Form(""),
    seats: str = Form("1"),
    purchase_date: str = Form(""),
    expiry_date: str = Form(""),
    purchase_price: str = Form(""),
    status: str = Form("active"),
    notes: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    lic = db.query(License).filter_by(id=pk).first()
    if not lic:
        return RedirectResponse("/licenses/", status_code=302)
    base = ctx(request, db)
    errors = {}
    if not name.strip():
        errors["name"] = ["To pole jest wymagane."]
    if errors:
        form_data = dict(name=name, vendor=vendor, license_key=license_key, seats=seats,
                         purchase_date=purchase_date, expiry_date=expiry_date,
                         purchase_price=purchase_price, status=status, notes=notes)
        return templates.TemplateResponse("license_form.html", {
            **base, "title": f"Edytuj {lic.asset_tag}", "object": lic,
            "status_choices": License.STATUS_CHOICES,
            "errors": errors, "form_data": form_data,
        }, status_code=400)

    lic.name = name.strip()
    lic.vendor = vendor.strip()
    lic.license_key = license_key.strip()
    lic.seats = int(seats) if seats.isdigit() else 1
    lic.purchase_date = _parse_date(purchase_date)
    lic.expiry_date = _parse_date(expiry_date)
    lic.purchase_price = _parse_decimal(purchase_price)
    lic.status = status
    lic.notes = notes.strip()
    db.commit()
    add_message(request, f"Licencja {lic.asset_tag} zaktualizowana.")
    return RedirectResponse(f"/licenses/{lic.id}/", status_code=302)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.get("/{pk}/delete/", name="license-delete")
async def license_delete_get(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    lic = db.query(License).filter_by(id=pk).first()
    if not lic:
        return RedirectResponse("/licenses/", status_code=302)
    base = ctx(request, db)
    return templates.TemplateResponse("confirm_delete.html", {
        **base,
        "object_name": f"{lic.asset_tag} — {lic.name}",
        "cancel_url": f"/licenses/{pk}/",
    })


@router.post("/{pk}/delete/", name="license-delete-post")
async def license_delete_post(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    lic = db.query(License).filter_by(id=pk).first()
    if lic:
        tag = lic.asset_tag
        db.delete(lic)
        db.commit()
        add_message(request, f"Licencja {tag} usunięta.")
    return RedirectResponse("/licenses/", status_code=302)


# ── Assign ────────────────────────────────────────────────────────────────────

@router.post("/{pk}/assign/", name="license-assign")
async def license_assign(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    form = await request.form()
    verify_csrf(request, form.get("csrf_token", ""))
    lic = db.query(License).filter_by(id=pk).first()
    if lic:
        user_ids = [int(uid) for uid in form.getlist("users") if uid.isdigit()]
        users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
        lic.assigned_users = users
        db.commit()
        add_message(request, "Przypisanie licencji zaktualizowane.")
    return RedirectResponse(f"/licenses/{pk}/", status_code=302)
