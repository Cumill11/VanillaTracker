import json
from datetime import date as parse_date
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Request, Depends, Form, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import verify_csrf
from app.deps import ctx, login_required
from app.flash import add_message
from app.models import Asset, AssetCounter, AssetHistory, Category, Department, Settings, User
from app.pagination import paginate
from app.label_pdf import generate_labels_pdf

router = APIRouter(prefix="/assets")
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


def _categories_json(db: Session) -> str:
    cats = db.query(Category).all()
    return json.dumps({str(c.id): c.slug for c in cats})


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


def _parse_int(s: str):
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _validate_asset(data: dict) -> dict:
    errors = {}
    if not data.get("name", "").strip():
        errors["name"] = ["To pole jest wymagane."]
    if _parse_int(data.get("category_id", "")) is None:
        errors["category"] = ["To pole jest wymagane."]
    if not data.get("manufacturer", "").strip():
        errors["manufacturer"] = ["To pole jest wymagane."]
    if not data.get("model_name", "").strip():
        errors["model_name"] = ["To pole jest wymagane."]
    return errors


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/", name="asset-list")
async def asset_list(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    q: str = "",
    category: str = "",
    status: str = "",
    sort: str = "tag_number",
    page: int = 1,
):
    base = ctx(request, db)
    qs = db.query(Asset)
    if q:
        qs = qs.filter(or_(
            Asset.asset_tag.ilike(f"%{q}%"),
            Asset.name.ilike(f"%{q}%"),
            Asset.serial_number.ilike(f"%{q}%"),
            Asset.manufacturer.ilike(f"%{q}%"),
            Asset.model_name.ilike(f"%{q}%"),
        ))
    if category:
        qs = qs.filter(Asset.category_id == category)
    if status:
        qs = qs.filter(Asset.status == status)
    sort_map = {
        "tag_number": Asset.tag_number,
        "-tag_number": Asset.tag_number.desc(),
        "name": Asset.name,
        "-name": Asset.name.desc(),
        "status": Asset.status,
        "category__name": None,
    }
    order_col = sort_map.get(sort, Asset.tag_number)
    if order_col is not None:
        qs = qs.order_by(order_col)

    pagination = paginate(qs, page)
    return templates.TemplateResponse(request, "asset_list.html", {
        **base,
        "assets": pagination.items,
        "pagination": pagination,
        "categories": db.query(Category).all(),
        "status_choices": Asset.STATUS_CHOICES,
        "current_q": q,
        "current_category": category,
        "current_status": status,
        "current_sort": sort,
    })


# ── Create ────────────────────────────────────────────────────────────────────

@router.get("/new/", name="asset-create")
async def asset_create_get(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    base = ctx(request, db)
    return templates.TemplateResponse(request, "asset_form.html", {
        **base,
        "title": "Dodaj sprzęt",
        "categories": db.query(Category).order_by(Category.name).all(),
        "departments": db.query(Department).order_by(Department.name).all(),
        "status_choices": Asset.STATUS_CHOICES,
        "categories_json": _categories_json(db),
        "errors": {},
        "form_data": {},
    })


@router.post("/new/", name="asset-create-post")
async def asset_create_post(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    name: str = Form(""),
    category_id: str = Form(""),
    manufacturer: str = Form(""),
    model_name: str = Form(""),
    serial_number: str = Form(""),
    purchase_date: str = Form(""),
    purchase_price: str = Form(""),
    warranty_expiry: str = Form(""),
    status: str = Form("available"),
    location: str = Form(""),
    notes: str = Form(""),
    cpu: str = Form(""),
    ram: str = Form(""),
    storage: str = Form(""),
    phone_number: str = Form(""),
    ink_type: str = Form(""),
    department_id: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    base = ctx(request, db)
    data = dict(
        name=name, category_id=category_id, manufacturer=manufacturer,
        model_name=model_name,
    )
    errors = _validate_asset(data)
    if errors:
        form_data = {
            "name": name, "category_id": category_id, "manufacturer": manufacturer,
            "model_name": model_name, "serial_number": serial_number,
            "purchase_date": purchase_date, "purchase_price": purchase_price,
            "warranty_expiry": warranty_expiry, "status": status,
            "location": location, "notes": notes,
            "cpu": cpu, "ram": ram, "storage": storage,
            "phone_number": phone_number, "ink_type": ink_type,
            "department_id": department_id,
        }
        return templates.TemplateResponse(request, "asset_form.html", {
            **base, "title": "Dodaj sprzęt",
            "categories": db.query(Category).order_by(Category.name).all(),
            "departments": db.query(Department).order_by(Department.name).all(),
            "status_choices": Asset.STATUS_CHOICES,
            "categories_json": _categories_json(db),
            "errors": errors, "form_data": form_data,
        }, status_code=400)

    num, tag = _next_tag(db)
    asset = Asset(
        asset_tag=tag, tag_number=num,
        name=name.strip(), category_id=_parse_int(category_id),
        manufacturer=manufacturer.strip(), model_name=model_name.strip(),
        serial_number=serial_number.strip() or None,
        purchase_date=_parse_date(purchase_date),
        purchase_price=_parse_decimal(purchase_price),
        warranty_expiry=_parse_date(warranty_expiry),
        status=status, location=location.strip(), notes=notes.strip(),
        cpu=cpu.strip(), ram=ram.strip(), storage=storage.strip(),
        phone_number=phone_number.strip(), ink_type=ink_type.strip(),
        department_id=_parse_int(department_id),
    )
    db.add(asset)
    db.flush()
    db.add(AssetHistory(
        asset_id=asset.id, action=AssetHistory.ACTION_NOTE,
        performed_by_id=user.id, note="Sprzęt dodany do systemu.",
    ))
    db.commit()
    add_message(request, f"Sprzęt {asset.asset_tag} został dodany.")
    return RedirectResponse(f"/assets/{asset.id}/", status_code=302)


# ── Labels bulk (musi być przed /{pk}/) ───────────────────────────────────────

@router.post("/labels/", name="asset-labels-bulk")
async def asset_labels_bulk(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    form = await request.form()
    verify_csrf(request, form.get("csrf_token", ""))
    pks = form.getlist("asset_pks")
    if not pks:
        add_message(request, "Nie wybrano żadnego sprzętu do wydruku.")
        return RedirectResponse("/assets/", status_code=302)
    ids = [_parse_int(p) for p in pks]
    ids = [i for i in ids if i is not None]
    assets = db.query(Asset).filter(Asset.id.in_(ids)).order_by(Asset.tag_number).all()
    if not assets:
        add_message(request, "Nie znaleziono wybranego sprzętu.")
        return RedirectResponse("/assets/", status_code=302)
    base_url = str(request.base_url).rstrip("/")
    pdf = generate_labels_pdf(assets, base_url)
    return Response(
        content=pdf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="etykiety.pdf"'},
    )


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{pk}/", name="asset-detail")
async def asset_detail(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    asset = db.query(Asset).filter_by(id=pk).first()
    if not asset:
        return RedirectResponse("/assets/", status_code=302)
    base = ctx(request, db)
    history = (
        db.query(AssetHistory)
        .filter_by(asset_id=pk)
        .order_by(AssetHistory.created_at.desc())
        .all()
    )
    users_qs = db.query(User).filter_by(is_active=True).order_by(User.last_name, User.first_name).all()
    return templates.TemplateResponse(request, "asset_detail.html", {
        **base,
        "asset": asset,
        "history": history,
        "users": users_qs,
        "departments": db.query(Department).order_by(Department.name).all(),
    })


# ── Update ────────────────────────────────────────────────────────────────────

@router.get("/{pk}/edit/", name="asset-update")
async def asset_update_get(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    asset = db.query(Asset).filter_by(id=pk).first()
    if not asset:
        return RedirectResponse("/assets/", status_code=302)
    base = ctx(request, db)
    form_data = {
        "name": asset.name, "category_id": str(asset.category_id or ""),
        "manufacturer": asset.manufacturer, "model_name": asset.model_name,
        "serial_number": asset.serial_number or "",
        "purchase_date": asset.purchase_date.isoformat() if asset.purchase_date else "",
        "purchase_price": str(asset.purchase_price) if asset.purchase_price else "",
        "warranty_expiry": asset.warranty_expiry.isoformat() if asset.warranty_expiry else "",
        "status": asset.status, "location": asset.location, "notes": asset.notes,
        "cpu": asset.cpu or "", "ram": asset.ram or "", "storage": asset.storage or "",
        "phone_number": asset.phone_number or "", "ink_type": asset.ink_type or "",
        "department_id": str(asset.department_id or ""),
    }
    return templates.TemplateResponse(request, "asset_form.html", {
        **base,
        "title": f"Edytuj {asset.asset_tag}",
        "object": asset,
        "categories": db.query(Category).order_by(Category.name).all(),
        "departments": db.query(Department).order_by(Department.name).all(),
        "status_choices": Asset.STATUS_CHOICES,
        "categories_json": _categories_json(db),
        "errors": {}, "form_data": form_data,
    })


@router.post("/{pk}/edit/", name="asset-update-post")
async def asset_update_post(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    name: str = Form(""),
    category_id: str = Form(""),
    manufacturer: str = Form(""),
    model_name: str = Form(""),
    serial_number: str = Form(""),
    purchase_date: str = Form(""),
    purchase_price: str = Form(""),
    warranty_expiry: str = Form(""),
    status: str = Form("available"),
    location: str = Form(""),
    notes: str = Form(""),
    cpu: str = Form(""),
    ram: str = Form(""),
    storage: str = Form(""),
    phone_number: str = Form(""),
    ink_type: str = Form(""),
    department_id: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    asset = db.query(Asset).filter_by(id=pk).first()
    if not asset:
        return RedirectResponse("/assets/", status_code=302)
    base = ctx(request, db)

    data = dict(name=name, category_id=category_id, manufacturer=manufacturer, model_name=model_name)
    errors = _validate_asset(data)
    if errors:
        form_data = {
            "name": name, "category_id": category_id, "manufacturer": manufacturer,
            "model_name": model_name, "serial_number": serial_number,
            "purchase_date": purchase_date, "purchase_price": purchase_price,
            "warranty_expiry": warranty_expiry, "status": status,
            "location": location, "notes": notes,
            "cpu": cpu, "ram": ram, "storage": storage,
            "phone_number": phone_number, "ink_type": ink_type,
            "department_id": department_id,
        }
        return templates.TemplateResponse(request, "asset_form.html", {
            **base, "title": f"Edytuj {asset.asset_tag}", "object": asset,
            "categories": db.query(Category).order_by(Category.name).all(),
            "departments": db.query(Department).order_by(Department.name).all(),
            "status_choices": Asset.STATUS_CHOICES,
            "categories_json": _categories_json(db),
            "errors": errors, "form_data": form_data,
        }, status_code=400)

    asset.name = name.strip()
    asset.category_id = _parse_int(category_id)
    asset.manufacturer = manufacturer.strip()
    asset.model_name = model_name.strip()
    asset.serial_number = serial_number.strip() or None
    asset.purchase_date = _parse_date(purchase_date)
    asset.purchase_price = _parse_decimal(purchase_price)
    asset.warranty_expiry = _parse_date(warranty_expiry)
    asset.status = status
    asset.location = location.strip()
    asset.notes = notes.strip()
    asset.cpu = cpu.strip()
    asset.ram = ram.strip()
    asset.storage = storage.strip()
    asset.phone_number = phone_number.strip()
    asset.ink_type = ink_type.strip()
    asset.department_id = _parse_int(department_id)
    db.commit()
    add_message(request, f"Sprzęt {asset.asset_tag} zaktualizowany.")
    return RedirectResponse(f"/assets/{asset.id}/", status_code=302)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.get("/{pk}/delete/", name="asset-delete")
async def asset_delete_get(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    asset = db.query(Asset).filter_by(id=pk).first()
    if not asset:
        return RedirectResponse("/assets/", status_code=302)
    base = ctx(request, db)
    return templates.TemplateResponse(request, "confirm_delete.html", {
        **base,
        "object_name": f"{asset.asset_tag} — {asset.name}",
        "cancel_url": f"/assets/{pk}/",
    })


@router.post("/{pk}/delete/", name="asset-delete-post")
async def asset_delete_post(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    asset = db.query(Asset).filter_by(id=pk).first()
    if asset:
        tag = asset.asset_tag
        db.delete(asset)
        db.commit()
        add_message(request, f"Sprzęt {tag} usunięty.")
    return RedirectResponse("/assets/", status_code=302)


# ── Assign ────────────────────────────────────────────────────────────────────

@router.post("/{pk}/assign/", name="asset-assign")
async def asset_assign(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    assign_user_id: str = Form(""),
    assigned_date: str = Form(""),
    note: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    asset = db.query(Asset).filter_by(id=pk).first()
    if asset and _parse_int(assign_user_id):
        assigned_user = db.query(User).filter_by(id=_parse_int(assign_user_id)).first()
        if assigned_user:
            asset.assigned_to_id = assigned_user.id
            asset.assigned_date = _parse_date(assigned_date)
            asset.status = Asset.STATUS_ASSIGNED
            db.add(AssetHistory(
                asset_id=asset.id, action=AssetHistory.ACTION_ASSIGN,
                user_id=assigned_user.id, performed_by_id=user.id, note=note,
            ))
            db.commit()
            add_message(request, f"{asset.asset_tag} przypisany do {assigned_user.get_full_name()}.")
    return RedirectResponse(f"/assets/{pk}/", status_code=302)


# ── Return ────────────────────────────────────────────────────────────────────

@router.post("/{pk}/return/", name="asset-return")
async def asset_return(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    note: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    asset = db.query(Asset).filter_by(id=pk).first()
    if asset:
        prev_user_id = asset.assigned_to_id
        db.add(AssetHistory(
            asset_id=asset.id, action=AssetHistory.ACTION_RETURN,
            user_id=prev_user_id, performed_by_id=user.id, note=note,
        ))
        asset.assigned_to_id = None
        asset.assigned_date = None
        asset.status = Asset.STATUS_AVAILABLE
        db.commit()
        add_message(request, f"{asset.asset_tag} zwrócony.")
    return RedirectResponse(f"/assets/{pk}/", status_code=302)


# ── Assign to department ──────────────────────────────────────────────────────

@router.post("/{pk}/assign-dept/", name="asset-assign-dept")
async def asset_assign_dept(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    department_id: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    asset = db.query(Asset).filter_by(id=pk).first()
    if asset:
        new_dept_id = _parse_int(department_id)
        asset.department_id = new_dept_id
        dept = db.query(Department).filter_by(id=new_dept_id).first() if new_dept_id else None
        note = f"Dział: {dept.name}" if dept else "Usunięto przypisanie do działu"
        db.add(AssetHistory(
            asset_id=asset.id, action=AssetHistory.ACTION_ASSIGN_DEPT,
            performed_by_id=user.id, note=note,
        ))
        db.commit()
        if dept:
            add_message(request, f"{asset.asset_tag} przypisany do działu {dept.name}.")
        else:
            add_message(request, f"{asset.asset_tag} — usunięto przypisanie do działu.")
    return RedirectResponse(f"/assets/{pk}/", status_code=302)


# ── Label single ─────────────────────────────────────────────────────────────

@router.get("/{pk}/label/", name="asset-label")
async def asset_label(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    asset = db.query(Asset).filter_by(id=pk).first()
    if not asset:
        return RedirectResponse("/assets/", status_code=302)
    base_url = str(request.base_url).rstrip("/")
    pdf = generate_labels_pdf([asset], base_url)
    return Response(
        content=pdf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{asset.asset_tag}.pdf"'},
    )
