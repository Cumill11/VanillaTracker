import os
import sys
from datetime import date as date_type
from markupsafe import Markup
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

from app.database import engine, Base, SessionLocal
from app.deps import _Redirect
from app.routers import auth, dashboard, assets, licenses, users, categories
from app.routers import setup as setup_module
from app.models import Category, AssetCounter

_DEFAULT_SECRET = "dev-secret-key-change-in-production"
SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET)
if SECRET_KEY == _DEFAULT_SECRET:
    print(
        "WARNING: SECRET_KEY is set to the default insecure value. "
        "Set the SECRET_KEY environment variable before deploying!",
        file=sys.stderr,
    )

# Create tables, seed required data, detect first-run
Base.metadata.create_all(bind=engine)

_CATEGORIES = [
    ("Laptop", "laptop"), ("Komputer stacjonarny", "desktop"),
    ("Monitor", "monitor"), ("Telefon", "phone"), ("Tablet", "tablet"),
    ("Drukarka", "printer"), ("Sprzęt sieciowy", "network"),
    ("Peryferia", "peripheral"), ("Licencja", "license"), ("Inne", "other"),
]

_db = SessionLocal()
try:
    for _name, _slug in _CATEGORIES:
        if not _db.query(Category).filter_by(slug=_slug).first():
            _db.add(Category(name=_name, slug=_slug))
    if not _db.query(AssetCounter).filter_by(id=1).first():
        _db.add(AssetCounter(id=1, last_number=0))
    _db.commit()
    setup_module.setup_needed = setup_module.check_setup_needed(_db)
finally:
    _db.close()

HTTPS_ONLY = os.getenv("HTTPS_ONLY", "false").lower() == "true"

app = FastAPI(title="VanillaTracker")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="strict", https_only=HTTPS_ONLY)


@app.middleware("http")
async def setup_guard(request: Request, call_next):
    if setup_module.setup_needed:
        path = request.url.path
        if not path.startswith("/setup") and not path.startswith("/static"):
            return RedirectResponse("/setup/", status_code=302)
    return await call_next(request)

# Static files
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.autoescape = True


# ── Jinja2 filters & globals ──────────────────────────────────────────────────

def status_chip(status: str) -> Markup:
    colors = {
        "available": "#4CAF50", "assigned": "#2196F3",
        "maintenance": "#FF9800", "retired": "#F44336",
        "active": "#4CAF50", "expired": "#F44336", "inactive": "#9E9E9E",
    }
    labels = {
        "available": "Dostępny", "assigned": "Przypisany",
        "maintenance": "Serwis", "retired": "Wycofany",
        "active": "Aktywna", "expired": "Wygasła", "inactive": "Nieaktywna",
    }
    c = colors.get(status, "#9E9E9E")
    l = labels.get(status, status)
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


templates.env.filters["status_chip"] = status_chip
templates.env.filters["category_icon"] = category_icon
templates.env.filters["date_fmt"] = date_fmt
templates.env.filters["default_dash"] = default_dash
templates.env.globals["date_type"] = date_type

# Share templates instance with all routers
for router_module in [auth, dashboard, assets, licenses, users, categories, setup_module]:
    router_module.templates = templates


# ── Exception handler for login redirect ─────────────────────────────────────

@app.exception_handler(_Redirect)
async def redirect_handler(request: Request, exc: _Redirect):
    return RedirectResponse(exc.url, status_code=302)


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(setup_module.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(assets.router)
app.include_router(licenses.router)
app.include_router(users.router)
app.include_router(categories.router)
