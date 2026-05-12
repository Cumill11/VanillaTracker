"""Optional helper — creates tables and seeds categories/counter outside of uvicorn."""
import os
from dotenv import load_dotenv
load_dotenv()

from app.database import engine, SessionLocal, Base
from app.models import Category, AssetCounter

Base.metadata.create_all(bind=engine)

CATEGORIES = [
    ("Laptop", "laptop"), ("Komputer stacjonarny", "desktop"),
    ("Monitor", "monitor"), ("Telefon", "phone"), ("Tablet", "tablet"),
    ("Drukarka", "printer"), ("Sprzęt sieciowy", "network"),
    ("Peryferia", "peripheral"), ("Licencja", "license"), ("Inne", "other"),
]

db = SessionLocal()
try:
    for name, slug in CATEGORIES:
        if not db.query(Category).filter_by(slug=slug).first():
            db.add(Category(name=name, slug=slug))
    if not db.query(AssetCounter).filter_by(id=1).first():
        db.add(AssetCounter(id=1, last_number=0))
    db.commit()
    print("Baza danych zainicjalizowana. Uruchom aplikację i wejdź na /setup/ aby utworzyć administratora.")
finally:
    db.close()
