"""
VanillaTracker — wersja Flask (migracja 1:1 z FastAPI).

Uruchomienie:
    python app.py
"""
import io
import os
import re
import sys
import json
import unicodedata
from datetime import date, timedelta, date as parse_date, date as date_type
from decimal import Decimal, InvalidOperation
from functools import wraps
from urllib.parse import urlparse

import bcrypt
import secrets
from dotenv import load_dotenv
from markupsafe import Markup
from flask import (
    Flask, request, session, redirect, render_template, abort, g, Response,
)
from sqlalchemy import or_, func

# .env wczytujemy z katalogu oryginalnego projektu (nadrzędnego względem vanillatracker)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from database import engine, SessionLocal, Base
from models import (
    Asset, AssetCounter, AssetHistory, Category, Department, License,
    LoginAttempt, Settings, TagPool, User, UserProfile, utcnow,
)
from pagination import paginate
from label_pdf import generate_labels_pdf
from i18n import TRANSLATIONS


# ── Konfiguracja sekretów ─────────────────────────────────────────────────────

_DEFAULT_SECRET = "dev-secret-key-change-in-production"
SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET)
if SECRET_KEY == _DEFAULT_SECRET:
    print(
        "WARNING: SECRET_KEY is set to the default insecure value. "
        "Set the SECRET_KEY environment variable before deploying!",
        file=sys.stderr,
    )

HTTPS_ONLY = os.getenv("HTTPS_ONLY", "false").lower() == "true"


# ── Aplikacja Flask ───────────────────────────────────────────────────────────

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
    static_url_path="/static",
)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=HTTPS_ONLY,
    JSON_AS_ASCII=False,
)
app.jinja_env.autoescape = True


# ── Sesja bazy danych (per-request) ───────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = SessionLocal()
    return g.db


@app.teardown_appcontext
def _close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ── Migracje / seed danych / wykrycie pierwszego uruchomienia ─────────────────

def _init_database() -> None:
    """Tworzy brakujące tabele i uzupełnia wymagane dane startowe.

    Oryginał używał Alembica; tutaj create_all wystarcza — dla istniejącej,
    już zmigrowanej bazy jest to operacja pusta, a dla świeżej bazy tworzy
    finalny schemat zgodny z modelami.
    """
    Base.metadata.create_all(engine)

    categories = [
        ("Laptop", "laptop"), ("Komputer stacjonarny", "desktop"),
        ("Monitor", "monitor"), ("Telefon", "phone"), ("Tablet", "tablet"),
        ("Drukarka", "printer"), ("Sprzęt sieciowy", "network"),
        ("Peryferia", "peripheral"), ("Licencja", "license"), ("Inne", "other"),
    ]
    db = SessionLocal()
    try:
        for name, slug in categories:
            if not db.query(Category).filter_by(slug=slug).first():
                db.add(Category(name=name, slug=slug))
        if not db.query(AssetCounter).filter_by(id=1).first():
            db.add(AssetCounter(id=1, last_number=0))
        db.commit()
        return check_setup_needed(db)
    finally:
        db.close()


def check_setup_needed(db) -> bool:
    return not db.query(User).filter_by(is_superuser=True).first()


# ── Uwierzytelnianie ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def authenticate(db, username: str, password: str):
    user = db.query(User).filter_by(username=username).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None


def login_user(user: User) -> None:
    session["user_id"] = user.id


def logout_user() -> None:
    session.clear()


def get_current_user(db):
    uid = session.get("user_id")
    if not uid:
        return None
    return db.query(User).filter_by(id=uid).first()


# ── CSRF ──────────────────────────────────────────────────────────────────────

def csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def verify_csrf(token: str) -> None:
    expected = session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(expected, token):
        abort(403, description="Nieprawidłowy token CSRF")


# ── Komunikaty (flash) ────────────────────────────────────────────────────────

def add_message(text: str) -> None:
    msgs = session.get("_messages", [])
    msgs.append(text)
    session["_messages"] = msgs


def get_messages() -> list:
    return session.pop("_messages", [])


# ── Wymaganie logowania ───────────────────────────────────────────────────────

def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not get_current_user(get_db()):
            return redirect(f"/login/?next={request.path}")
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = get_current_user(get_db())
        if not user:
            return redirect(f"/login/?next={request.path}")
        if not user.is_superuser:
            add_message("Tylko administrator ma dostęp do tej operacji.")
            return redirect("/")
        return view(*args, **kwargs)
    return wrapper


# ── Filtry / globalne Jinja2 ──────────────────────────────────────────────────

def status_chip(status: str, label: str = "") -> Markup:
    colors = {
        "available": "#4CAF50", "assigned": "#2196F3",
        "maintenance": "#FF9800", "retired": "#F44336",
        "active": "#4CAF50", "expired": "#F44336", "inactive": "#9E9E9E",
    }
    fallback_labels = {
        "available": "Dostępny", "assigned": "Przypisany",
        "maintenance": "Serwis", "retired": "Wycofany",
        "active": "Aktywna", "expired": "Wygasła", "inactive": "Nieaktywna",
    }
    c = colors.get(status, "#9E9E9E")
    l = label if label else fallback_labels.get(status, status)
    return Markup(
        f'<span class="status-chip" style="background:{c}20;color:{c};border:1px solid {c}40">'
        f'{l}</span>'
    )


def category_icon(slug: str) -> str:
    icons = {
        "laptop": "laptop", "desktop": "desktop_windows",
        "monitor": "monitor", "phone": "smartphone",
        "tablet": "tablet", "printer": "print",
        "network": "router", "peripheral": "keyboard",
        "license": "key", "other": "devices_other",
    }
    return icons.get(slug, "devices_other")


def date_fmt(value, fmt: str = "%d.%m.%Y") -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    try:
        return value.strftime(fmt)
    except Exception:
        return str(value)


def default_dash(value) -> str:
    if value is None or value == "" or value == 0:
        return "—"
    return str(value)


app.jinja_env.filters["status_chip"] = status_chip
app.jinja_env.filters["category_icon"] = category_icon
app.jinja_env.filters["date_fmt"] = date_fmt
app.jinja_env.filters["default_dash"] = default_dash
app.jinja_env.globals["date_type"] = date_type


# ── Kontekst szablonów ────────────────────────────────────────────────────────

@app.context_processor
def inject_base_context():
    db = get_db()
    user = get_current_user(db)
    path = request.path

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

    lang = request.cookies.get("lang", "pl")
    if lang not in TRANSLATIONS:
        lang = "pl"

    return {
        "user": user,
        "messages": get_messages(),
        "csrf_token": csrf_token(),
        "active": active,
        "lang": lang,
        "t": TRANSLATIONS[lang],
    }


# ── Strażnik pierwszego uruchomienia ──────────────────────────────────────────

setup_needed: bool = False


@app.before_request
def _setup_guard():
    if setup_needed:
        path = request.path
        if not path.startswith("/setup") and not path.startswith("/static"):
            return redirect("/setup/")


# ── Strony błędów ─────────────────────────────────────────────────────────────

@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(429)
def _handle_http_error(e):
    lang = request.cookies.get("lang", "pl")
    if lang not in TRANSLATIONS:
        lang = "pl"
    tr = TRANSLATIONS[lang]
    title = tr.get(f"error_{e.code}_title", tr["error_title"])
    message = tr.get(f"error_{e.code}_msg", tr["error_unknown"])
    return render_template(
        "error.html", code=e.code, title=title, message=message,
    ), e.code


# ── Pomocnicze parsery ────────────────────────────────────────────────────────

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


def _parse_int(s):
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _next_tag(db) -> tuple:
    s = db.query(Settings).filter_by(key="tag_prefix").first()
    prefix = s.value if s else "BS"
    pooled = db.query(TagPool).order_by(TagPool.tag_number).first()
    if pooled is not None:
        num = pooled.tag_number
        db.delete(pooled)
        db.flush()
        return num, f"{prefix}-{num:05d}"
    counter = db.query(AssetCounter).filter_by(id=1).with_for_update().first()
    if counter is None:
        counter = AssetCounter(id=1, last_number=0)
        db.add(counter)
        db.flush()
    counter.last_number += 1
    db.flush()
    return counter.last_number, f"{prefix}-{counter.last_number:05d}"


def _categories_json(db) -> str:
    cats = db.query(Category).all()
    return json.dumps({str(c.id): c.slug for c in cats})


def _validate_asset(data: dict) -> dict:
    errors = {}
    if _parse_int(data.get("category_id", "")) is None:
        errors["category"] = ["To pole jest wymagane."]
    if not data.get("manufacturer", "").strip():
        errors["manufacturer"] = ["To pole jest wymagane."]
    if not data.get("model_name", "").strip():
        errors["model_name"] = ["To pole jest wymagane."]
    return errors


def _effective_status(expiry_date, manual_status: str) -> str:
    if expiry_date and expiry_date < parse_date.today():
        return License.STATUS_EXPIRED
    if manual_status in (License.STATUS_ACTIVE, License.STATUS_INACTIVE):
        return manual_status
    return License.STATUS_ACTIVE


# ── Setup ─────────────────────────────────────────────────────────────────────

@app.route("/setup/", methods=["GET"], endpoint="setup")
def setup_get():
    if not setup_needed:
        return redirect("/")
    return render_template("setup.html", errors={})


@app.route("/setup/", methods=["POST"], endpoint="setup-post")
def setup_post():
    global setup_needed
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()

    username = request.form.get("username", "")
    password = request.form.get("password", "")
    password2 = request.form.get("password2", "")
    email = request.form.get("email", "")
    first_name = request.form.get("first_name", "")
    last_name = request.form.get("last_name", "")
    tag_prefix = request.form.get("tag_prefix", "").strip().upper()

    errors = {}
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
    if not re.match(r"^[A-Z]{2,4}$", tag_prefix):
        errors["tag_prefix"] = "Prefiks musi składać się z 2–4 liter (A–Z)."

    if errors:
        return render_template(
            "setup.html", errors=errors, username=username, email=email,
            first_name=first_name, last_name=last_name, tag_prefix=tag_prefix,
        ), 400

    user = User(
        username=username, email=email, first_name=first_name,
        last_name=last_name, password_hash=hash_password(password),
        is_superuser=True,
    )
    db.add(user)
    db.add(Settings(key="tag_prefix", value=tag_prefix))
    db.flush()
    db.add(UserProfile(user_id=user.id))
    db.commit()

    setup_needed = False
    return redirect("/login/")


# ── Logowanie / wylogowanie ───────────────────────────────────────────────────

_RATE_LIMIT = 5
_RATE_WINDOW = 300  # 5 minut


def _check_rate_limit(db, ip: str) -> bool:
    cutoff = utcnow() - timedelta(seconds=_RATE_WINDOW)
    db.query(LoginAttempt).filter(LoginAttempt.attempted_at < cutoff).delete()
    recent = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.ip == ip, LoginAttempt.attempted_at >= cutoff)
        .count()
    )
    if recent >= _RATE_LIMIT:
        db.commit()
        return False
    db.add(LoginAttempt(ip=ip))
    db.commit()
    return True


def _safe_redirect(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc:
        return "/"
    return url or "/"


@app.route("/login/", methods=["GET"], endpoint="login")
def login_get():
    if get_current_user(get_db()):
        return redirect("/")
    return render_template("login.html", errors={})


@app.route("/login/", methods=["POST"], endpoint="login-post")
def login_post():
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    next_url = request.form.get("next", "/")

    ip = request.remote_addr or "unknown"
    if not _check_rate_limit(db, ip):
        abort(429, description="Zbyt wiele prób logowania. Spróbuj ponownie za kilka minut.")

    user = authenticate(db, username, password)
    if not user:
        return render_template(
            "login.html",
            errors={"__all__": ["Nieprawidłowy login lub hasło."]},
            username=username,
        ), 400

    user.last_login = utcnow()
    db.commit()
    login_user(user)
    return redirect(_safe_redirect(next_url))


@app.route("/logout/", methods=["POST"], endpoint="logout")
def logout():
    verify_csrf(request.form.get("csrf_token", ""))
    logout_user()
    return redirect("/login/")


# ── Przełącznik języka ────────────────────────────────────────────────────────

@app.route("/lang/<code>/", endpoint="set_lang")
def set_lang(code):
    if code not in ("pl", "en"):
        code = "pl"
    next_url = request.args.get("next", "/")
    parsed = urlparse(next_url)
    safe_next = next_url if (not parsed.scheme and not parsed.netloc) else "/"
    response = redirect(safe_next or "/")
    response.set_cookie(
        "lang", code, max_age=365 * 24 * 3600, httponly=True, samesite="Strict",
    )
    return response


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/", endpoint="dashboard")
@login_required
def dashboard():
    db = get_db()
    today = date.today()

    categories = (
        db.query(Category, func.count(Asset.id).label("asset_count"))
        .outerjoin(Asset)
        .group_by(Category.id)
        .order_by(func.count(Asset.id).desc())
        .all()
    )
    cat_list = []
    for cat, cnt in categories:
        cat.asset_count = cnt
        cat_list.append(cat)

    expiring_warranties = (
        db.query(Asset)
        .filter(Asset.warranty_expiry >= today,
                Asset.warranty_expiry <= today + timedelta(days=60))
        .order_by(Asset.warranty_expiry)
        .limit(5).all()
    )
    expiring_licenses = (
        db.query(License)
        .filter(License.expiry_date >= today,
                License.status == License.STATUS_ACTIVE)
        .order_by(License.expiry_date)
        .limit(5).all()
    )
    recent_history = (
        db.query(AssetHistory)
        .order_by(AssetHistory.created_at.desc())
        .limit(10).all()
    )

    return render_template(
        "dashboard.html",
        total_assets=db.query(Asset).count(),
        assigned_assets=db.query(Asset).filter_by(status=Asset.STATUS_ASSIGNED).count(),
        available_assets=db.query(Asset).filter_by(status=Asset.STATUS_AVAILABLE).count(),
        maintenance_assets=db.query(Asset).filter_by(status=Asset.STATUS_MAINTENANCE).count(),
        total_users=db.query(User).count(),
        total_licenses=db.query(License).count(),
        active_licenses=db.query(License).filter_by(status=License.STATUS_ACTIVE).count(),
        categories=cat_list,
        expiring_warranties=expiring_warranties,
        expiring_licenses=expiring_licenses,
        recent_history=recent_history,
    )


# ── Sprzęt: lista ─────────────────────────────────────────────────────────────

@app.route("/assets/", endpoint="asset-list")
@login_required
def asset_list():
    db = get_db()
    q = request.args.get("q", "")
    category = request.args.get("category", "")
    status = request.args.get("status", "")
    sort = request.args.get("sort", "tag_number")
    page = request.args.get("page", 1, type=int)

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
    return render_template(
        "asset_list.html",
        assets=pagination.items,
        pagination=pagination,
        categories=db.query(Category).all(),
        status_choices=Asset.STATUS_CHOICES,
        current_q=q,
        current_category=category,
        current_status=status,
        current_sort=sort,
    )


# ── Sprzęt: tworzenie ─────────────────────────────────────────────────────────

@app.route("/assets/new/", methods=["GET"], endpoint="asset-create")
@login_required
def asset_create_get():
    db = get_db()
    return render_template(
        "asset_form.html",
        title="Dodaj sprzęt",
        categories=db.query(Category).order_by(Category.name).all(),
        categories_json=_categories_json(db),
        errors={}, form_data={},
    )


@app.route("/assets/new/", methods=["POST"], endpoint="asset-create-post")
@login_required
def asset_create_post():
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    user = get_current_user(db)
    f = request.form

    name = f.get("name", "")
    category_id = f.get("category_id", "")
    manufacturer = f.get("manufacturer", "")
    model_name = f.get("model_name", "")
    serial_number = f.get("serial_number", "")
    purchase_date = f.get("purchase_date", "")
    purchase_price = f.get("purchase_price", "")
    warranty_expiry = f.get("warranty_expiry", "")
    notes = f.get("notes", "")
    cpu = f.get("cpu", "")
    ram = f.get("ram", "")
    storage = f.get("storage", "")
    phone_number = f.get("phone_number", "")
    ink_type = f.get("ink_type", "")

    errors = _validate_asset(dict(
        name=name, category_id=category_id, manufacturer=manufacturer,
        model_name=model_name,
    ))
    if errors:
        form_data = {
            "name": name, "category_id": category_id, "manufacturer": manufacturer,
            "model_name": model_name, "serial_number": serial_number,
            "purchase_date": purchase_date, "purchase_price": purchase_price,
            "warranty_expiry": warranty_expiry, "notes": notes,
            "cpu": cpu, "ram": ram, "storage": storage,
            "phone_number": phone_number, "ink_type": ink_type,
        }
        return render_template(
            "asset_form.html", title="Dodaj sprzęt",
            categories=db.query(Category).order_by(Category.name).all(),
            categories_json=_categories_json(db),
            errors=errors, form_data=form_data,
        ), 400

    final_name = name.strip() or f"{manufacturer.strip()} {model_name.strip()}".strip()
    num, tag = _next_tag(db)
    asset = Asset(
        asset_tag=tag, tag_number=num,
        name=final_name, category_id=_parse_int(category_id),
        manufacturer=manufacturer.strip(), model_name=model_name.strip(),
        serial_number=serial_number.strip() or None,
        purchase_date=_parse_date(purchase_date),
        purchase_price=_parse_decimal(purchase_price),
        warranty_expiry=_parse_date(warranty_expiry),
        status=Asset.STATUS_AVAILABLE, notes=notes.strip(),
        cpu=cpu.strip(), ram=ram.strip(), storage=storage.strip(),
        phone_number=phone_number.strip(), ink_type=ink_type.strip(),
    )
    db.add(asset)
    db.flush()
    db.add(AssetHistory(
        asset_id=asset.id, action=AssetHistory.ACTION_NOTE,
        performed_by_id=user.id, note="Sprzęt dodany do systemu.",
    ))
    db.commit()
    add_message(f"Sprzęt {asset.asset_tag} został dodany.")
    return redirect(f"/assets/{asset.id}/")


# ── Sprzęt: etykiety zbiorcze ─────────────────────────────────────────────────

@app.route("/assets/labels/", methods=["POST"], endpoint="asset-labels-bulk")
@login_required
def asset_labels_bulk():
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    pks = request.form.getlist("asset_pks")
    if not pks:
        add_message("Nie wybrano żadnego sprzętu do wydruku.")
        return redirect("/assets/")
    ids = [_parse_int(p) for p in pks]
    ids = [i for i in ids if i is not None]
    assets = db.query(Asset).filter(Asset.id.in_(ids)).order_by(Asset.tag_number).all()
    if not assets:
        add_message("Nie znaleziono wybranego sprzętu.")
        return redirect("/assets/")
    base_url = request.url_root.rstrip("/")
    pdf = generate_labels_pdf(assets, base_url)
    return Response(
        pdf.read(),
        mimetype="application/pdf",
        headers={"Content-Disposition": 'inline; filename="etykiety.pdf"'},
    )


# ── Sprzęt: szczegóły ─────────────────────────────────────────────────────────

@app.route("/assets/<int:pk>/", endpoint="asset-detail")
@login_required
def asset_detail(pk):
    db = get_db()
    asset = db.query(Asset).filter_by(id=pk).first()
    if not asset:
        return redirect("/assets/")
    history = (
        db.query(AssetHistory)
        .filter_by(asset_id=pk)
        .order_by(AssetHistory.created_at.desc())
        .all()
    )
    users_qs = db.query(User).order_by(User.last_name, User.first_name).all()
    return render_template(
        "asset_detail.html",
        asset=asset,
        history=history,
        users=users_qs,
        departments=db.query(Department).order_by(Department.name).all(),
    )


# ── Sprzęt: edycja ────────────────────────────────────────────────────────────

@app.route("/assets/<int:pk>/edit/", methods=["GET"], endpoint="asset-update")
@login_required
def asset_update_get(pk):
    db = get_db()
    asset = db.query(Asset).filter_by(id=pk).first()
    if not asset:
        return redirect("/assets/")
    form_data = {
        "name": asset.name, "category_id": str(asset.category_id or ""),
        "manufacturer": asset.manufacturer, "model_name": asset.model_name,
        "serial_number": asset.serial_number or "",
        "purchase_date": asset.purchase_date.isoformat() if asset.purchase_date else "",
        "purchase_price": str(asset.purchase_price) if asset.purchase_price else "",
        "warranty_expiry": asset.warranty_expiry.isoformat() if asset.warranty_expiry else "",
        "notes": asset.notes,
        "cpu": asset.cpu or "", "ram": asset.ram or "", "storage": asset.storage or "",
        "phone_number": asset.phone_number or "", "ink_type": asset.ink_type or "",
    }
    return render_template(
        "asset_form.html",
        title=f"Edytuj {asset.asset_tag}",
        object=asset,
        categories=db.query(Category).order_by(Category.name).all(),
        categories_json=_categories_json(db),
        errors={}, form_data=form_data,
    )


@app.route("/assets/<int:pk>/edit/", methods=["POST"], endpoint="asset-update-post")
@login_required
def asset_update_post(pk):
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    asset = db.query(Asset).filter_by(id=pk).first()
    if not asset:
        return redirect("/assets/")
    f = request.form

    name = f.get("name", "")
    category_id = f.get("category_id", "")
    manufacturer = f.get("manufacturer", "")
    model_name = f.get("model_name", "")
    serial_number = f.get("serial_number", "")
    purchase_date = f.get("purchase_date", "")
    purchase_price = f.get("purchase_price", "")
    warranty_expiry = f.get("warranty_expiry", "")
    notes = f.get("notes", "")
    cpu = f.get("cpu", "")
    ram = f.get("ram", "")
    storage = f.get("storage", "")
    phone_number = f.get("phone_number", "")
    ink_type = f.get("ink_type", "")

    errors = _validate_asset(dict(
        name=name, category_id=category_id, manufacturer=manufacturer,
        model_name=model_name,
    ))
    if errors:
        form_data = {
            "name": name, "category_id": category_id, "manufacturer": manufacturer,
            "model_name": model_name, "serial_number": serial_number,
            "purchase_date": purchase_date, "purchase_price": purchase_price,
            "warranty_expiry": warranty_expiry, "notes": notes,
            "cpu": cpu, "ram": ram, "storage": storage,
            "phone_number": phone_number, "ink_type": ink_type,
        }
        return render_template(
            "asset_form.html", title=f"Edytuj {asset.asset_tag}", object=asset,
            categories=db.query(Category).order_by(Category.name).all(),
            categories_json=_categories_json(db),
            errors=errors, form_data=form_data,
        ), 400

    asset.name = name.strip() or f"{manufacturer.strip()} {model_name.strip()}".strip()
    asset.category_id = _parse_int(category_id)
    asset.manufacturer = manufacturer.strip()
    asset.model_name = model_name.strip()
    asset.serial_number = serial_number.strip() or None
    asset.purchase_date = _parse_date(purchase_date)
    asset.purchase_price = _parse_decimal(purchase_price)
    asset.warranty_expiry = _parse_date(warranty_expiry)
    asset.notes = notes.strip()
    asset.cpu = cpu.strip()
    asset.ram = ram.strip()
    asset.storage = storage.strip()
    asset.phone_number = phone_number.strip()
    asset.ink_type = ink_type.strip()
    db.commit()
    add_message(f"Sprzęt {asset.asset_tag} zaktualizowany.")
    return redirect(f"/assets/{asset.id}/")


# ── Sprzęt: usuwanie ──────────────────────────────────────────────────────────

@app.route("/assets/<int:pk>/delete/", methods=["GET"], endpoint="asset-delete")
@login_required
def asset_delete_get(pk):
    db = get_db()
    asset = db.query(Asset).filter_by(id=pk).first()
    if not asset:
        return redirect("/assets/")
    return render_template(
        "confirm_delete.html",
        object_name=f"{asset.asset_tag} — {asset.name}",
        cancel_url=f"/assets/{pk}/",
    )


@app.route("/assets/<int:pk>/delete/", methods=["POST"], endpoint="asset-delete-post")
@login_required
def asset_delete_post(pk):
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    asset = db.query(Asset).filter_by(id=pk).first()
    if asset:
        tag = asset.asset_tag
        db.add(TagPool(tag_number=asset.tag_number))
        db.delete(asset)
        db.commit()
        add_message(f"Sprzęt {tag} usunięty.")
    return redirect("/assets/")


# ── Sprzęt: przypisanie ───────────────────────────────────────────────────────

@app.route("/assets/<int:pk>/assign/", methods=["POST"], endpoint="asset-assign")
@login_required
def asset_assign(pk):
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    user = get_current_user(db)
    asset = db.query(Asset).filter_by(id=pk).first()
    assign_user_id = request.form.get("assign_user_id", "")
    assigned_date = request.form.get("assigned_date", "")
    note = request.form.get("note", "")
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
            add_message(f"{asset.asset_tag} przypisany do {assigned_user.get_full_name()}.")
    return redirect(f"/assets/{pk}/")


# ── Sprzęt: zwrot ─────────────────────────────────────────────────────────────

@app.route("/assets/<int:pk>/return/", methods=["POST"], endpoint="asset-return")
@login_required
def asset_return(pk):
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    user = get_current_user(db)
    note = request.form.get("note", "")
    asset = db.query(Asset).filter_by(id=pk).first()
    if asset:
        prev_user_id = asset.assigned_to_id
        db.add(AssetHistory(
            asset_id=asset.id, action=AssetHistory.ACTION_RETURN,
            user_id=prev_user_id, performed_by_id=user.id, note=note,
        ))
        asset.assigned_to_id = None
        asset.assigned_date = None
        asset.status = Asset.STATUS_ASSIGNED if asset.department_id else Asset.STATUS_AVAILABLE
        db.commit()
        add_message(f"{asset.asset_tag} zwrócony.")
    return redirect(f"/assets/{pk}/")


# ── Sprzęt: przypisanie do działu ─────────────────────────────────────────────

@app.route("/assets/<int:pk>/assign-dept/", methods=["POST"], endpoint="asset-assign-dept")
@login_required
def asset_assign_dept(pk):
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    user = get_current_user(db)
    department_id = request.form.get("department_id", "")
    asset = db.query(Asset).filter_by(id=pk).first()
    if asset:
        new_dept_id = _parse_int(department_id)
        asset.department_id = new_dept_id
        dept = db.query(Department).filter_by(id=new_dept_id).first() if new_dept_id else None
        if dept:
            asset.status = Asset.STATUS_ASSIGNED
            note = f"Dział: {dept.name}"
            add_message(f"{asset.asset_tag} przypisany do działu {dept.name}.")
        else:
            if not asset.assigned_to_id:
                asset.status = Asset.STATUS_AVAILABLE
            note = "Usunięto przypisanie do działu"
            add_message(f"{asset.asset_tag} — usunięto przypisanie do działu.")
        db.add(AssetHistory(
            asset_id=asset.id, action=AssetHistory.ACTION_ASSIGN_DEPT,
            performed_by_id=user.id, note=note,
        ))
        db.commit()
    return redirect(f"/assets/{pk}/")


# ── Sprzęt: szybka zmiana statusu ─────────────────────────────────────────────

_QUICK_STATUS_NOTES = {
    Asset.STATUS_AVAILABLE: "Oznaczono jako dostępny.",
    Asset.STATUS_MAINTENANCE: "Przekazano do serwisu.",
    Asset.STATUS_RETIRED: "Wycofano z użytku.",
}

_STATUS_QUESTIONS = {
    Asset.STATUS_MAINTENANCE: "Czy przekazać sprzęt do serwisu?",
    Asset.STATUS_RETIRED: "Czy wycofać sprzęt z użytku?",
}


@app.route("/assets/<int:pk>/status/", methods=["GET"], endpoint="asset-status-confirm")
@login_required
def asset_status_confirm(pk):
    db = get_db()
    status = request.args.get("status", "")
    asset = db.query(Asset).filter_by(id=pk).first()
    if not asset or status not in _STATUS_QUESTIONS or asset.assigned_to_id:
        return redirect(f"/assets/{pk}/")
    return render_template(
        "confirm_status.html",
        asset=asset,
        new_status=status,
        question=_STATUS_QUESTIONS[status],
    )


@app.route("/assets/<int:pk>/status/", methods=["POST"], endpoint="asset-status")
@login_required
def asset_status(pk):
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    user = get_current_user(db)
    status = request.form.get("status", "")
    asset = db.query(Asset).filter_by(id=pk).first()
    if asset and status in _QUICK_STATUS_NOTES and not asset.assigned_to_id:
        if asset.status != status:
            note = _QUICK_STATUS_NOTES[status]
            asset.status = status
            db.add(AssetHistory(
                asset_id=asset.id, action=AssetHistory.ACTION_STATUS,
                performed_by_id=user.id, note=note,
            ))
            db.commit()
            add_message(f"{asset.asset_tag}: {note}")
    return redirect(f"/assets/{pk}/")


# ── Sprzęt: etykieta pojedyncza ───────────────────────────────────────────────

@app.route("/assets/<int:pk>/label/", endpoint="asset-label")
@login_required
def asset_label(pk):
    db = get_db()
    asset = db.query(Asset).filter_by(id=pk).first()
    if not asset:
        return redirect("/assets/")
    base_url = request.url_root.rstrip("/")
    pdf = generate_labels_pdf([asset], base_url)
    return Response(
        pdf.read(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{asset.asset_tag}.pdf"'},
    )


# ── Licencje: lista ───────────────────────────────────────────────────────────

@app.route("/licenses/", endpoint="license-list")
@login_required
def license_list():
    db = get_db()
    q = request.args.get("q", "")
    status = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)

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
    return render_template(
        "license_list.html",
        licenses=pagination.items,
        pagination=pagination,
        status_choices=License.STATUS_CHOICES,
        current_q=q,
        current_status=status,
    )


# ── Licencje: tworzenie ───────────────────────────────────────────────────────

@app.route("/licenses/new/", methods=["GET"], endpoint="license-create")
@login_required
def license_create_get():
    return render_template(
        "license_form.html",
        title="Dodaj licencję",
        status_choices=License.MANUAL_STATUS_CHOICES,
        errors={}, form_data={},
    )


@app.route("/licenses/new/", methods=["POST"], endpoint="license-create-post")
@login_required
def license_create_post():
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    f = request.form
    name = f.get("name", "")
    vendor = f.get("vendor", "")
    license_key = f.get("license_key", "")
    seats = f.get("seats", "1")
    purchase_date = f.get("purchase_date", "")
    expiry_date = f.get("expiry_date", "")
    purchase_price = f.get("purchase_price", "")
    status = f.get("status", "active")
    notes = f.get("notes", "")

    errors = {}
    if not name.strip():
        errors["name"] = ["To pole jest wymagane."]
    if errors:
        form_data = dict(name=name, vendor=vendor, license_key=license_key, seats=seats,
                         purchase_date=purchase_date, expiry_date=expiry_date,
                         purchase_price=purchase_price, status=status, notes=notes)
        return render_template(
            "license_form.html", title="Dodaj licencję",
            status_choices=License.MANUAL_STATUS_CHOICES,
            errors=errors, form_data=form_data,
        ), 400

    num, tag = _next_tag(db)
    parsed_expiry = _parse_date(expiry_date)
    lic = License(
        asset_tag=tag, tag_number=num,
        name=name.strip(), vendor=vendor.strip(), license_key=license_key.strip(),
        seats=int(seats) if seats.isdigit() else 1,
        purchase_date=_parse_date(purchase_date),
        expiry_date=parsed_expiry,
        purchase_price=_parse_decimal(purchase_price),
        status=_effective_status(parsed_expiry, status), notes=notes.strip(),
    )
    db.add(lic)
    db.commit()
    add_message(f"Licencja {lic.asset_tag} dodana.")
    return redirect(f"/licenses/{lic.id}/")


# ── Licencje: szczegóły ───────────────────────────────────────────────────────

@app.route("/licenses/<int:pk>/", endpoint="license-detail")
@login_required
def license_detail(pk):
    db = get_db()
    lic = db.query(License).filter_by(id=pk).first()
    if not lic:
        return redirect("/licenses/")
    history = (
        db.query(AssetHistory)
        .filter_by(license_id=pk)
        .order_by(AssetHistory.created_at.desc())
        .all()
    )
    all_users = db.query(User).order_by(User.last_name, User.first_name).all()
    assigned_ids = {u.id for u in lic.assigned_users}
    return render_template(
        "license_detail.html",
        license=lic,
        history=history,
        all_users=all_users,
        assigned_ids=assigned_ids,
    )


# ── Licencje: edycja ──────────────────────────────────────────────────────────

@app.route("/licenses/<int:pk>/edit/", methods=["GET"], endpoint="license-update")
@login_required
def license_update_get(pk):
    db = get_db()
    lic = db.query(License).filter_by(id=pk).first()
    if not lic:
        return redirect("/licenses/")
    form_data = {
        "name": lic.name, "vendor": lic.vendor, "license_key": lic.license_key,
        "seats": str(lic.seats),
        "purchase_date": lic.purchase_date.isoformat() if lic.purchase_date else "",
        "expiry_date": lic.expiry_date.isoformat() if lic.expiry_date else "",
        "purchase_price": str(lic.purchase_price) if lic.purchase_price else "",
        "status": lic.status if lic.status in (License.STATUS_ACTIVE, License.STATUS_INACTIVE) else License.STATUS_ACTIVE,
        "notes": lic.notes,
    }
    return render_template(
        "license_form.html",
        title=f"Edytuj {lic.asset_tag}",
        object=lic,
        status_choices=License.MANUAL_STATUS_CHOICES,
        errors={}, form_data=form_data,
    )


@app.route("/licenses/<int:pk>/edit/", methods=["POST"], endpoint="license-update-post")
@login_required
def license_update_post(pk):
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    lic = db.query(License).filter_by(id=pk).first()
    if not lic:
        return redirect("/licenses/")
    f = request.form
    name = f.get("name", "")
    vendor = f.get("vendor", "")
    license_key = f.get("license_key", "")
    seats = f.get("seats", "1")
    purchase_date = f.get("purchase_date", "")
    expiry_date = f.get("expiry_date", "")
    purchase_price = f.get("purchase_price", "")
    status = f.get("status", "active")
    notes = f.get("notes", "")

    errors = {}
    if not name.strip():
        errors["name"] = ["To pole jest wymagane."]
    if errors:
        form_data = dict(name=name, vendor=vendor, license_key=license_key, seats=seats,
                         purchase_date=purchase_date, expiry_date=expiry_date,
                         purchase_price=purchase_price, status=status, notes=notes)
        return render_template(
            "license_form.html", title=f"Edytuj {lic.asset_tag}", object=lic,
            status_choices=License.MANUAL_STATUS_CHOICES,
            errors=errors, form_data=form_data,
        ), 400

    lic.name = name.strip()
    lic.vendor = vendor.strip()
    lic.license_key = license_key.strip()
    lic.seats = int(seats) if seats.isdigit() else 1
    lic.purchase_date = _parse_date(purchase_date)
    lic.expiry_date = _parse_date(expiry_date)
    lic.purchase_price = _parse_decimal(purchase_price)
    lic.status = _effective_status(lic.expiry_date, status)
    lic.notes = notes.strip()
    db.commit()
    add_message(f"Licencja {lic.asset_tag} zaktualizowana.")
    return redirect(f"/licenses/{lic.id}/")


# ── Licencje: usuwanie ────────────────────────────────────────────────────────

@app.route("/licenses/<int:pk>/delete/", methods=["GET"], endpoint="license-delete")
@login_required
def license_delete_get(pk):
    db = get_db()
    lic = db.query(License).filter_by(id=pk).first()
    if not lic:
        return redirect("/licenses/")
    return render_template(
        "confirm_delete.html",
        object_name=f"{lic.asset_tag} — {lic.name}",
        cancel_url=f"/licenses/{pk}/",
    )


@app.route("/licenses/<int:pk>/delete/", methods=["POST"], endpoint="license-delete-post")
@login_required
def license_delete_post(pk):
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    lic = db.query(License).filter_by(id=pk).first()
    if lic:
        tag = lic.asset_tag
        db.add(TagPool(tag_number=lic.tag_number))
        db.delete(lic)
        db.commit()
        add_message(f"Licencja {tag} usunięta.")
    return redirect("/licenses/")


# ── Licencje: przypisanie użytkowników ────────────────────────────────────────

@app.route("/licenses/<int:pk>/assign/", methods=["POST"], endpoint="license-assign")
@login_required
def license_assign(pk):
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    lic = db.query(License).filter_by(id=pk).first()
    if lic:
        user_ids = [int(uid) for uid in request.form.getlist("users") if uid.isdigit()]
        users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
        lic.assigned_users = users
        db.commit()
        add_message("Przypisanie licencji zaktualizowane.")
    return redirect(f"/licenses/{pk}/")


# ── Użytkownicy ───────────────────────────────────────────────────────────────

def _auto_username(db, first: str, last: str) -> str:
    def norm(s):
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
        return re.sub(r"[^\w]", "", s).lower()
    base = f"{norm(first)}.{norm(last)}" if last else norm(first) or "user"
    username, n = base, 1
    while db.query(User).filter_by(username=username).first():
        username, n = f"{base}{n}", n + 1
    return username


@app.route("/users/", endpoint="user-list")
@admin_required
def user_list():
    db = get_db()
    q = request.args.get("q", "")
    department = request.args.get("department", "")
    page = request.args.get("page", 1, type=int)

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
    qs = qs.order_by(User.last_name, User.first_name)
    pagination = paginate(qs, page)

    asset_counts = dict(
        db.query(Asset.assigned_to_id, func.count(Asset.id))
        .filter(Asset.status == Asset.STATUS_ASSIGNED)
        .group_by(Asset.assigned_to_id)
        .all()
    )
    for u in pagination.items:
        u.asset_count = asset_counts.get(u.id, 0)

    return render_template(
        "user_list.html",
        users=pagination.items,
        pagination=pagination,
        departments=db.query(Department).order_by(Department.name).all(),
        current_q=q,
        current_dept=department,
    )


@app.route("/users/new/", methods=["GET"], endpoint="user-create")
@admin_required
def user_create_get():
    db = get_db()
    return render_template(
        "user_form.html",
        title="Dodaj użytkownika",
        departments=db.query(Department).order_by(Department.name).all(),
        errors={}, form_data={},
    )


@app.route("/users/new/", methods=["POST"], endpoint="user-create-post")
@admin_required
def user_create_post():
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    f = request.form
    first_name = f.get("first_name", "")
    last_name = f.get("last_name", "")
    email = f.get("email", "")
    department_id = f.get("department_id", "")
    position = f.get("position", "")
    phone = f.get("phone", "")
    can_login = f.get("can_login", "")
    username = f.get("username", "")
    password1 = f.get("password1", "")
    password2 = f.get("password2", "")

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
        return render_template(
            "user_form.html", title="Dodaj użytkownika",
            departments=db.query(Department).order_by(Department.name).all(),
            errors=errors, form_data=form_data,
        ), 400

    uname = username.strip() if can_login_bool else _auto_username(db, first_name, last_name)
    new_user = User(
        username=uname,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip(),
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
    add_message(f"Użytkownik {new_user.get_full_name()} dodany.")
    return redirect("/users/")


@app.route("/users/<int:pk>/", endpoint="user-detail")
@login_required
def user_detail(pk):
    db = get_db()
    profile_user = db.query(User).filter_by(id=pk).first()
    if not profile_user:
        return redirect("/users/")
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
    return render_template(
        "user_detail.html",
        profile_user=profile_user,
        assigned_assets=assigned_assets,
        licenses=licenses,
        history=history,
    )


@app.route("/users/<int:pk>/edit/", methods=["GET"], endpoint="user-update")
@admin_required
def user_update_get(pk):
    db = get_db()
    edit_user = db.query(User).filter_by(id=pk).first()
    if not edit_user:
        return redirect("/users/")
    profile = edit_user.profile
    form_data = {
        "first_name": edit_user.first_name,
        "last_name": edit_user.last_name,
        "email": edit_user.email,
        "department_id": str(profile.department_id) if profile and profile.department_id else "",
        "position": profile.position if profile else "",
        "phone": profile.phone if profile else "",
    }
    return render_template(
        "user_form.html",
        title=f"Edytuj {edit_user.get_full_name()}",
        edit_user=edit_user,
        departments=db.query(Department).order_by(Department.name).all(),
        errors={}, form_data=form_data,
    )


@app.route("/users/<int:pk>/edit/", methods=["POST"], endpoint="user-update-post")
@admin_required
def user_update_post(pk):
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    edit_user = db.query(User).filter_by(id=pk).first()
    if not edit_user:
        return redirect("/users/")

    edit_user.first_name = request.form.get("first_name", "").strip()
    edit_user.last_name = request.form.get("last_name", "").strip()
    edit_user.email = request.form.get("email", "").strip()

    department_id = request.form.get("department_id", "")
    position = request.form.get("position", "")
    phone = request.form.get("phone", "")

    profile = db.query(UserProfile).filter_by(user_id=pk).first()
    if not profile:
        profile = UserProfile(user_id=pk)
        db.add(profile)
    profile.department_id = int(department_id) if department_id else None
    profile.position = position.strip()
    profile.phone = phone.strip()
    db.commit()
    add_message("Użytkownik zaktualizowany.")
    return redirect("/users/")


@app.route("/users/<int:pk>/password/", methods=["GET"], endpoint="user-password")
@login_required
def user_password_get(pk):
    db = get_db()
    user = get_current_user(db)
    edit_user = db.query(User).filter_by(id=pk).first()
    if not edit_user:
        return redirect("/users/")
    if not user.is_superuser and user.id != pk:
        add_message("Nie masz uprawnień do zmiany hasła tego użytkownika.")
        return redirect(f"/users/{pk}/")
    return render_template(
        "user_password_form.html",
        edit_user=edit_user,
        require_current=not user.is_superuser,
        errors={},
    )


@app.route("/users/<int:pk>/password/", methods=["POST"], endpoint="user-password-post")
@login_required
def user_password_post(pk):
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    user = get_current_user(db)
    edit_user = db.query(User).filter_by(id=pk).first()
    if not edit_user:
        return redirect("/users/")
    if not user.is_superuser and user.id != pk:
        add_message("Nie masz uprawnień do zmiany hasła tego użytkownika.")
        return redirect(f"/users/{pk}/")

    require_current = not user.is_superuser
    current_password = request.form.get("current_password", "")
    password1 = request.form.get("password1", "")
    password2 = request.form.get("password2", "")
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
        return render_template(
            "user_password_form.html",
            edit_user=edit_user,
            require_current=require_current,
            errors=errors,
        ), 400

    edit_user.password_hash = hash_password(password1)
    db.commit()
    add_message(f"Hasło użytkownika {edit_user.get_full_name()} zostało zmienione.")
    return redirect(f"/users/{pk}/")


def _delete_blockers(db, pk: int) -> list:
    blockers = []
    asset_count = db.query(Asset).filter(Asset.assigned_to_id == pk).count()
    if asset_count:
        blockers.append(f"przypisany sprzęt ({asset_count})")
    license_count = (
        db.query(License).filter(License.assigned_users.any(User.id == pk)).count()
    )
    if license_count:
        blockers.append(f"przypisane licencje ({license_count})")
    return blockers


@app.route("/users/<int:pk>/delete/", methods=["GET"], endpoint="user-delete")
@admin_required
def user_delete_get(pk):
    db = get_db()
    user = get_current_user(db)
    edit_user = db.query(User).filter_by(id=pk).first()
    if not edit_user:
        return redirect("/users/")
    if user.id == pk:
        add_message("Nie możesz usunąć własnego konta.")
        return redirect(f"/users/{pk}/")
    blockers = _delete_blockers(db, pk)
    if blockers:
        add_message(
            f"Nie można usunąć pracownika {edit_user.get_full_name()} — "
            f"najpierw odepnij: {', '.join(blockers)}."
        )
        return redirect(f"/users/{pk}/")
    return render_template(
        "confirm_delete.html",
        object_name=edit_user.get_full_name(),
        cancel_url=f"/users/{pk}/",
    )


@app.route("/users/<int:pk>/delete/", methods=["POST"], endpoint="user-delete-post")
@admin_required
def user_delete_post(pk):
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    user = get_current_user(db)
    edit_user = db.query(User).filter_by(id=pk).first()
    if not edit_user:
        return redirect("/users/")
    if user.id == pk:
        add_message("Nie możesz usunąć własnego konta.")
        return redirect(f"/users/{pk}/")
    blockers = _delete_blockers(db, pk)
    if blockers:
        add_message(
            f"Nie można usunąć pracownika {edit_user.get_full_name()} — "
            f"najpierw odepnij: {', '.join(blockers)}."
        )
        return redirect(f"/users/{pk}/")

    name = edit_user.get_full_name()
    db.query(AssetHistory).filter_by(user_id=pk).update({"user_id": None})
    db.query(AssetHistory).filter_by(performed_by_id=pk).update({"performed_by_id": None})
    db.delete(edit_user)
    db.commit()
    add_message(f"Pracownik {name} został usunięty.")
    return redirect("/users/")


# ── Typy: kategorie i działy ──────────────────────────────────────────────────

@app.route("/categories/", endpoint="category-list")
@login_required
def category_list():
    db = get_db()
    categories = (
        db.query(Category, func.count(func.distinct(Asset.id)).label("asset_count"))
        .outerjoin(Category.assets)
        .group_by(Category.id)
        .order_by(Category.name)
        .all()
    )
    cat_list = []
    for cat, cnt in categories:
        cat.asset_count = cnt
        cat_list.append(cat)

    departments = (
        db.query(Department, func.count(UserProfile.id).label("user_count"))
        .outerjoin(UserProfile)
        .group_by(Department.id)
        .order_by(Department.name)
        .all()
    )
    dept_list = []
    for dept, cnt in departments:
        dept.user_count = cnt
        dept_list.append(dept)

    return render_template(
        "category_list.html",
        categories=cat_list,
        departments=dept_list,
    )


@app.route("/departments/new/", methods=["GET"], endpoint="department-create")
@login_required
def dept_create_get():
    return render_template(
        "department_form.html", title="Dodaj dział",
        errors={}, form_data={},
    )


@app.route("/departments/new/", methods=["POST"], endpoint="department-create-post")
@login_required
def dept_create_post():
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    name = request.form.get("name", "")
    errors = {}
    if not name.strip():
        errors["name"] = ["To pole jest wymagane."]
    if errors:
        return render_template(
            "department_form.html", title="Dodaj dział",
            errors=errors, form_data={"name": name},
        ), 400
    dept = Department(name=name.strip())
    db.add(dept)
    db.commit()
    add_message(f"Dział {dept.name} dodany.")
    return redirect("/categories/")


@app.route("/departments/<int:pk>/edit/", methods=["GET"], endpoint="department-update")
@login_required
def dept_update_get(pk):
    db = get_db()
    dept = db.query(Department).filter_by(id=pk).first()
    if not dept:
        return redirect("/categories/")
    return render_template(
        "department_form.html", title=f"Edytuj {dept.name}",
        object=dept,
        errors={}, form_data={"name": dept.name},
    )


@app.route("/departments/<int:pk>/edit/", methods=["POST"], endpoint="department-update-post")
@login_required
def dept_update_post(pk):
    verify_csrf(request.form.get("csrf_token", ""))
    db = get_db()
    dept = db.query(Department).filter_by(id=pk).first()
    if not dept:
        return redirect("/categories/")
    name = request.form.get("name", "")
    errors = {}
    if not name.strip():
        errors["name"] = ["To pole jest wymagane."]
    if errors:
        return render_template(
            "department_form.html", title=f"Edytuj {dept.name}", object=dept,
            errors=errors, form_data={"name": name},
        ), 400
    dept.name = name.strip()
    db.commit()
    add_message(f"Dział {dept.name} zaktualizowany.")
    return redirect("/categories/")


# ── Inicjalizacja i uruchomienie ──────────────────────────────────────────────

with app.app_context():
    setup_needed = _init_database()


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", "8000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
