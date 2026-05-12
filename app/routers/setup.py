import re
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Settings, User, UserProfile
from app.auth import hash_password, csrf_token as _csrf_token, verify_csrf

router = APIRouter()
templates: Jinja2Templates = None  # injected from main.py

setup_needed: bool = False


def check_setup_needed(db: Session) -> bool:
    return not db.query(User).filter_by(is_superuser=True).first()


def _ctx(request: Request) -> dict:
    return {"request": request, "csrf_token": _csrf_token(request)}


@router.get("/setup/", name="setup")
async def setup_get(request: Request):
    if not setup_needed:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "setup.html", {**_ctx(request), "errors": {}})


@router.post("/setup/", name="setup-post")
async def setup_post(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    email: str = Form(""),
    first_name: str = Form(""),
    last_name: str = Form(""),
    tag_prefix: str = Form(""),
    csrf_token: str = Form(""),
):
    global setup_needed
    verify_csrf(request, csrf_token)

    tag_prefix = tag_prefix.strip().upper()

    errors: dict[str, str] = {}
    if not username:
        errors["username"] = "Login jest wymagany."
    elif db.query(User).filter_by(username=username).first():
        errors["username"] = "Taka nazwa użytkownika już istnieje."
    if not password:
        errors["password"] = "Hasło jest wymagane."
    elif len(password) < 8:
        errors["password"] = "Hasło musi mieć co najmniej 8 znaków."
    elif password != password2:
        errors["password2"] = "Hasła nie są zgodne."
    if not re.match(r'^[A-Z]{2,4}$', tag_prefix):
        errors["tag_prefix"] = "Prefiks musi składać się z 2–4 liter (A–Z)."

    if errors:
        return templates.TemplateResponse(
            request,
            "setup.html",
            {
                **_ctx(request),
                "errors": errors,
                "username": username,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "tag_prefix": tag_prefix,
            },
            status_code=400,
        )

    user = User(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password_hash=hash_password(password),
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.add(Settings(key="tag_prefix", value=tag_prefix))
    db.flush()
    db.add(UserProfile(user_id=user.id))
    db.commit()

    setup_needed = False
    return RedirectResponse("/login/", status_code=302)
