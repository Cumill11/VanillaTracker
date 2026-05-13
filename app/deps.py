from fastapi import Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user, csrf_token as _csrf_token
from app.flash import get_messages
from app.models import User


def ctx(request: Request, db: Session = Depends(get_db)) -> dict:
    """Base template context: request, user, messages, csrf_token, active section."""
    user = get_current_user(request, db)
    path = request.url.path

    if path.startswith("/assets"):
        active = "assets"
    elif path.startswith("/licenses"):
        active = "licenses"
    elif path.startswith("/users"):
        active = "users"
    elif path.startswith("/categories") or path.startswith("/departments"):
        active = "categories"
    else:
        active = "dashboard"

    return {
        "request": request,
        "user": user,
        "messages": get_messages(request),
        "csrf_token": _csrf_token(request),
        "active": active,
    }


def login_required(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user:
        raise _Redirect(f"/login/?next={request.url.path}")
    return user


class _Redirect(Exception):
    def __init__(self, url: str):
        self.url = url
