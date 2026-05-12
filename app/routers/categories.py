from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import verify_csrf
from app.deps import ctx, login_required
from app.flash import add_message
from app.models import Asset, Category, Department, UserProfile

router = APIRouter()
templates: Jinja2Templates = None


@router.get("/categories/", name="category-list")
async def category_list(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    base = ctx(request, db)
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

    return templates.TemplateResponse(request, "category_list.html", {
        **base,
        "categories": cat_list,
        "departments": dept_list,
    })


# ── Departments ───────────────────────────────────────────────────────────────

@router.get("/departments/new/", name="department-create")
async def dept_create_get(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    base = ctx(request, db)
    return templates.TemplateResponse(request, "department_form.html", {
        **base, "title": "Dodaj dział",
        "errors": {}, "form_data": {},
    })


@router.post("/departments/new/", name="department-create-post")
async def dept_create_post(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    name: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    base = ctx(request, db)
    errors = {}
    if not name.strip():
        errors["name"] = ["To pole jest wymagane."]
    if errors:
        return templates.TemplateResponse(request, "department_form.html", {
            **base, "title": "Dodaj dział",
            "errors": errors, "form_data": {"name": name},
        }, status_code=400)
    dept = Department(name=name.strip())
    db.add(dept)
    db.commit()
    add_message(request, f"Dział {dept.name} dodany.")
    return RedirectResponse("/categories/", status_code=302)


@router.get("/departments/{pk}/edit/", name="department-update")
async def dept_update_get(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    dept = db.query(Department).filter_by(id=pk).first()
    if not dept:
        return RedirectResponse("/categories/", status_code=302)
    base = ctx(request, db)
    return templates.TemplateResponse(request, "department_form.html", {
        **base, "title": f"Edytuj {dept.name}",
        "object": dept,
        "errors": {}, "form_data": {"name": dept.name},
    })


@router.post("/departments/{pk}/edit/", name="department-update-post")
async def dept_update_post(
    pk: int, request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
    name: str = Form(""),
    csrf_token: str = Form(""),
):
    verify_csrf(request, csrf_token)
    dept = db.query(Department).filter_by(id=pk).first()
    if not dept:
        return RedirectResponse("/categories/", status_code=302)
    base = ctx(request, db)
    errors = {}
    if not name.strip():
        errors["name"] = ["To pole jest wymagane."]
    if errors:
        return templates.TemplateResponse(request, "department_form.html", {
            **base, "title": f"Edytuj {dept.name}", "object": dept,
            "errors": errors, "form_data": {"name": name},
        }, status_code=400)
    dept.name = name.strip()
    db.commit()
    add_message(request, f"Dział {dept.name} zaktualizowany.")
    return RedirectResponse("/categories/", status_code=302)
