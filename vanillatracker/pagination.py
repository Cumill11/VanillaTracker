from dataclasses import dataclass
from typing import Any


@dataclass
class Page:
    items: list
    total: int
    page: int
    per_page: int
    num_pages: int
    has_prev: bool
    has_next: bool


def paginate(query, page: int, per_page: int = 25) -> Page:
    total = query.count()
    num_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, num_pages))
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return Page(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        num_pages=num_pages,
        has_prev=page > 1,
        has_next=page < num_pages,
    )
