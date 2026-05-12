from datetime import date, timedelta
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ctx, login_required
from app.models import Asset, License, Category, User, AssetHistory

router = APIRouter()
templates: Jinja2Templates = None


@router.get("/", name="dashboard")
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    base = ctx(request, db)
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

    return templates.TemplateResponse(request, "dashboard.html", {
        **base,
        "total_assets":      db.query(Asset).count(),
        "assigned_assets":   db.query(Asset).filter_by(status=Asset.STATUS_ASSIGNED).count(),
        "available_assets":  db.query(Asset).filter_by(status=Asset.STATUS_AVAILABLE).count(),
        "maintenance_assets": db.query(Asset).filter_by(status=Asset.STATUS_MAINTENANCE).count(),
        "total_users":       db.query(User).filter_by(is_active=True).count(),
        "total_licenses":    db.query(License).count(),
        "active_licenses":   db.query(License).filter_by(status=License.STATUS_ACTIVE).count(),
        "categories":        cat_list,
        "expiring_warranties": expiring_warranties,
        "expiring_licenses": expiring_licenses,
        "recent_history":    recent_history,
    })
