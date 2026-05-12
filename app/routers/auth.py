import time
from collections import defaultdict
from urllib.parse import urlparse
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import authenticate, login_user, logout_user, verify_csrf
from app.deps import ctx
from app.flash import add_message

router = APIRouter()
templates: Jinja2Templates = None  # injected from main.py

_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 5
_RATE_WINDOW = 300  # 5 minutes


def _check_rate_limit(ip: str) -> bool:
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _RATE_WINDOW]
    if len(_login_attempts[ip]) >= _RATE_LIMIT:
        return False
    _login_attempts[ip].append(now)
    return True


def _safe_redirect(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc:
        return "/"
    return url or "/"


@router.get("/login/", name="login")
async def login_get(request: Request, db: Session = Depends(get_db)):
    base = ctx(request, db)
    if base["user"]:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {**base, "errors": {}})


@router.post("/login/", name="login-post")
async def login_post(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(""),
    password: str = Form(""),
    next: str = Form("/"),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    base = ctx(request, db)
    ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Zbyt wiele prób logowania. Spróbuj ponownie za kilka minut.")
    user = authenticate(db, username, password)
    if not user:
        return templates.TemplateResponse(
            request,
            "login.html",
            {**base, "errors": {"__all__": ["Nieprawidłowy login lub hasło."]},
             "username": username},
            status_code=400,
        )
    login_user(request, user)
    return RedirectResponse(_safe_redirect(next), status_code=302)


@router.post("/logout/", name="logout")
async def logout(request: Request, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    logout_user(request)
    return RedirectResponse("/login/", status_code=302)
