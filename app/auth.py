import secrets
import bcrypt
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter_by(username=username, is_active=True).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None


def login_user(request: Request, user: User) -> None:
    request.session["user_id"] = user.id


def logout_user(request: Request) -> None:
    request.session.clear()


def get_current_user(request: Request, db: Session) -> User | None:
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.query(User).filter_by(id=uid, is_active=True).first()


def require_user(request: Request, db: Session) -> User:
    user = get_current_user(request, db)
    if not user:
        raise NotAuthenticated()
    return user


class NotAuthenticated(Exception):
    pass


# ── CSRF ──────────────────────────────────────────────────────────────────────

def csrf_token(request: Request) -> str:
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = secrets.token_hex(32)
    return request.session["csrf_token"]


def verify_csrf(request: Request, token: str) -> None:
    expected = request.session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(expected, token):
        raise HTTPException(status_code=403, detail="Nieprawidłowy token CSRF")
