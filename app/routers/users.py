import re
import unicodedata
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import hash_password, verify_csrf, verify_password
from app.deps import ctx, login_required
from app.flash import add_message
from app.models import Asset, AssetHistory, Department, License, User, UserProfile
from app.pagination import paginate

router = APIRouter(prefix="/users")
templates: Jinja2Templates = None


def _auto_username(db: Session, first: str, last: str) -> str:
    def norm(s):
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
        return re.sub(r"[^\w]", "", s).lower()
    base = f"{norm(first)}.{norm(last)}" if last else norm(first) or "user"
    username, n = base, 1
    while db.query(User).filter_by(username=username).first():
        username, n = f"{base}{n}", n + 1
    return username


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/", name="user-list")
async def user_list(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    q: str = "",
    department: str = "",
    active: str = "1",
    page: int = 1,
):
    base = ctx(request, db)
    qs = db.query(User)
    if q:
        qs = qs.filter(or_(
            User.username.ilike(f"%{q}%"),
            User.first_name.ilike(f"%{q}%"),
            User.last_name.ilike(f"%{q}%"),
            User.email.ilike(f"%{q}%"),
        ))
    if department and department.isdigit():
        qs = qs.join(UserProfile).filter(UserProfile.department_id == int(department))
    if active == "1":
        qs = qs.filter(User.is_active == True)
    qs = qs.order_by(User.last_name, User.first_name)
    pagination = paginate(qs, page)

    # Annotate asset counts
    asset_counts = dict(
        db.query(Asset.assigned_to_id, func.count(Asset.id))
        .filter(Asset.status == Asset.STATUS_ASSIGNED)
        .group_by(Asset.assigned_to_id)
        .all()
    )
    for u in pagination.items:
        u.asset_count = asset_counts.get(u.id, 0)

    return templates.TemplateResponse(request, "user_list.html", {
        **base,
        "users": pagination.items,
        "pagination": pagination,
        "departments": db.query(Department).order_by(Department.name).all(),
        "current_q": q,
        "current_dept": department,
        "current_active": active,
    })


# ── Create ────────────────────────────────────────────────────────────────────

@router.get("/new/", name="user-create")
async def user_create_get(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    base = ctx(request, db)
    return templates.TemplateResponse(request, "user_form.html", {
        **base,
        "title": "Dodaj użytkownika",
        "departments": db.query(Department).order_by(Department.name).all(),
        "errors": {}, "form_data": {},
    })


@router.post("/new/", name="user-create-post")
async def user_create_post(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    first_name: str = Form(""),
    last_name: str = Form(""),
    email: str = Form(""),
    department_id: str = Form(""),
    position: str = Form(""),
    phone: str = Form(""),
    can_login: str = Form(""),
    username: str = Form(""),
    password1: str = Form(""),
    password2: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    base = ctx(request, db)
    errors = {}
    if not first_name.strip():
        errors["first_name"] = ["To pole jest wymagane."]
    if not last_name.strip():
        errors["last_name"] = ["To pole jest wymagane."]
    can_login_bool = bool(can_login)
    if can_login_bool:
        if not username.strip():
            errors["username"] = ["Login jest wymagany."]
        if not password1:
            errors["password1"] = ["Hasło jest wymagane."]
        elif len(password1) < 8:
            errors["password1"] = ["Hasło musi mieć co najmniej 8 znaków."]
        elif password1 != password2:
            errors["password2"] = ["Hasła nie są identyczne."]
        elif db.query(User).filter_by(username=username).first():
            errors["username"] = ["Ten login jest już zajęty."]

    if errors:
        form_data = dict(first_name=first_name, last_name=last_name, email=email,
                         department_id=department_id, position=position, phone=phone,
                         can_login=can_login, username=username)
        return templates.TemplateResponse(request, "user_form.html", {
            **base, "title": "Dodaj użytkownika",
            "departments": db.query(Department).order_by(Department.name).all(),
            "errors": errors, "form_data": form_data,
        }, status_code=400)

    uname = username.strip() if can_login_bool else _auto_username(db, first_name, last_name)
    new_user = User(
        username=uname,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip(),
        is_active=True,
        password_hash=hash_password(password1) if can_login_bool else "",
    )
    db.add(new_user)
    db.flush()
    profile = UserProfile(
        user_id=new_user.id,
        department_id=int(department_id) if department_id else None,
        position=position.strip(),
        phone=phone.strip(),
    )
    db.add(profile)
    db.commit()
    add_message(request, f"Użytkownik {new_user.get_full_name()} dodany.")
    return RedirectResponse("/users/", status_code=302)


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{pk}/", name="user-detail")
async def user_detail(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    profile_user = db.query(User).filter_by(id=pk).first()
    if not profile_user:
        return RedirectResponse("/users/", status_code=302)
    base = ctx(request, db)
    assigned_assets = (
        db.query(Asset)
        .filter(Asset.assigned_to_id == pk, Asset.status == Asset.STATUS_ASSIGNED)
        .order_by(Asset.tag_number).all()
    )
    licenses = db.query(License).filter(
        License.assigned_users.any(User.id == pk)
    ).all()
    history = (
        db.query(AssetHistory)
        .filter_by(user_id=pk)
        .order_by(AssetHistory.created_at.desc())
        .limit(20).all()
    )
    return templates.TemplateResponse(request, "user_detail.html", {
        **base,
        "profile_user": profile_user,
        "assigned_assets": assigned_assets,
        "licenses": licenses,
        "history": history,
    })


# ── Update ────────────────────────────────────────────────────────────────────

@router.get("/{pk}/edit/", name="user-update")
async def user_update_get(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    edit_user = db.query(User).filter_by(id=pk).first()
    if not edit_user:
        return RedirectResponse("/users/", status_code=302)
    base = ctx(request, db)
    profile = edit_user.profile
    form_data = {
        "first_name": edit_user.first_name,
        "last_name": edit_user.last_name,
        "email": edit_user.email,
        "is_active": "1" if edit_user.is_active else "",
        "department_id": str(profile.department_id) if profile and profile.department_id else "",
        "position": profile.position if profile else "",
        "phone": profile.phone if profile else "",
        "is_active_employee": "1" if (profile and profile.is_active_employee) else "",
    }
    return templates.TemplateResponse(request, "user_form.html", {
        **base,
        "title": f"Edytuj {edit_user.get_full_name()}",
        "edit_user": edit_user,
        "departments": db.query(Department).order_by(Department.name).all(),
        "errors": {}, "form_data": form_data,
    })


@router.post("/{pk}/edit/", name="user-update-post")
async def user_update_post(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    first_name: str = Form(""),
    last_name: str = Form(""),
    email: str = Form(""),
    is_active: str = Form(""),
    department_id: str = Form(""),
    position: str = Form(""),
    phone: str = Form(""),
    is_active_employee: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    edit_user = db.query(User).filter_by(id=pk).first()
    if not edit_user:
        return RedirectResponse("/users/", status_code=302)

    edit_user.first_name = first_name.strip()
    edit_user.last_name = last_name.strip()
    edit_user.email = email.strip()
    edit_user.is_active = bool(is_active)

    profile = db.query(UserProfile).filter_by(user_id=pk).first()
    if not profile:
        profile = UserProfile(user_id=pk)
        db.add(profile)
    profile.department_id = int(department_id) if department_id else None
    profile.position = position.strip()
    profile.phone = phone.strip()
    profile.is_active_employee = bool(is_active_employee)
    db.commit()
    add_message(request, "Użytkownik zaktualizowany.")
    return RedirectResponse("/users/", status_code=302)


# ── Change password ───────────────────────────────────────────────────────────

@router.get("/{pk}/password/", name="user-password")
async def user_password_get(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    edit_user = db.query(User).filter_by(id=pk).first()
    if not edit_user:
        return RedirectResponse("/users/", status_code=302)
    if not user.is_superuser and user.id != pk:
        add_message(request, "Nie masz uprawnień do zmiany hasła tego użytkownika.", "error")
        return RedirectResponse(f"/users/{pk}/", status_code=302)
    return templates.TemplateResponse(request, "user_password_form.html", {
        **ctx(request, db),
        "edit_user": edit_user,
        "require_current": not user.is_superuser,
        "errors": {},
    })


@router.post("/{pk}/password/", name="user-password-post")
async def user_password_post(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    current_password: str = Form(""),
    password1: str = Form(""),
    password2: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    edit_user = db.query(User).filter_by(id=pk).first()
    if not edit_user:
        return RedirectResponse("/users/", status_code=302)
    if not user.is_superuser and user.id != pk:
        add_message(request, "Nie masz uprawnień do zmiany hasła tego użytkownika.", "error")
        return RedirectResponse(f"/users/{pk}/", status_code=302)

    require_current = not user.is_superuser
    errors = {}

    if require_current and not verify_password(current_password, edit_user.password_hash):
        errors["current_password"] = ["Nieprawidłowe obecne hasło."]

    if not password1:
        errors["password1"] = ["Hasło jest wymagane."]
    elif len(password1) < 8:
        errors["password1"] = ["Hasło musi mieć co najmniej 8 znaków."]
    elif password1 != password2:
        errors["password2"] = ["Hasła nie są identyczne."]

    if errors:
        return templates.TemplateResponse(request, "user_password_form.html", {
            **ctx(request, db),
            "edit_user": edit_user,
            "require_current": require_current,
            "errors": errors,
        }, status_code=400)

    edit_user.password_hash = hash_password(password1)
    db.commit()
    add_message(request, f"Hasło użytkownika {edit_user.get_full_name()} zostało zmienione.")
    return RedirectResponse(f"/users/{pk}/", status_code=302)
