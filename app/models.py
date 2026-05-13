from datetime import datetime, date as date_type
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Date, Numeric,
    DateTime, ForeignKey, Table, func,
)
from sqlalchemy.orm import relationship
from app.database import Base


license_users = Table(
    "license_users",
    Base.metadata,
    Column("license_id", Integer, ForeignKey("licenses.id", ondelete="CASCADE")),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE")),
)


class Settings(Base):
    __tablename__ = "settings"
    key = Column(String(50), primary_key=True)
    value = Column(String(200), default="")


class AssetCounter(Base):
    __tablename__ = "asset_counter"
    id = Column(Integer, primary_key=True)
    last_number = Column(Integer, default=0, nullable=False)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    email = Column(String(254), default="")
    first_name = Column(String(150), default="")
    last_name = Column(String(150), default="")
    password_hash = Column(String(256), default="")
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    date_joined = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    profile = relationship(
        "UserProfile", back_populates="user", uselist=False,
        cascade="all, delete-orphan",
    )
    assigned_assets = relationship(
        "Asset", back_populates="assigned_to",
        foreign_keys="Asset.assigned_to_id",
    )
    licenses = relationship(
        "License", secondary=license_users, back_populates="assigned_users",
    )

    def get_full_name(self) -> str:
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.username

    def get_initials(self) -> str:
        name = self.get_full_name()
        return name[0].upper() if name else "?"


class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)

    profiles = relationship("UserProfile", back_populates="department")

    def __str__(self) -> str:
        return self.name


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    phone = Column(String(30), default="")
    position = Column(String(100), default="")
    is_active_employee = Column(Boolean, default=True)

    user = relationship("User", back_populates="profile")
    department = relationship("Department", back_populates="profiles")


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False)
    description = Column(Text, default="")

    assets = relationship("Asset", back_populates="category")

    def __str__(self) -> str:
        return self.name


class Asset(Base):
    __tablename__ = "assets"

    STATUS_AVAILABLE = "available"
    STATUS_ASSIGNED = "assigned"
    STATUS_MAINTENANCE = "maintenance"
    STATUS_RETIRED = "retired"

    STATUS_CHOICES = [
        ("available", "Dostępny"),
        ("assigned", "Przypisany"),
        ("maintenance", "Serwis"),
        ("retired", "Wycofany"),
    ]

    id = Column(Integer, primary_key=True)
    asset_tag = Column(String(12), unique=True, nullable=False, index=True)
    tag_number = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    manufacturer = Column(String(100), nullable=False, default="")
    model_name = Column(String(100), nullable=False, default="")
    serial_number = Column(String(150), nullable=True)
    purchase_date = Column(Date, nullable=True)
    purchase_price = Column(Numeric(10, 2), nullable=True)
    warranty_expiry = Column(Date, nullable=True)
    status = Column(String(20), default="available", index=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_date = Column(Date, nullable=True)
    location = Column(String(200), default="")
    notes = Column(Text, default="")
    cpu = Column(String(200), default="")
    ram = Column(String(100), default="")
    storage = Column(String(200), default="")
    phone_number = Column(String(50), default="")
    ink_type = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("Category", back_populates="assets")
    assigned_to = relationship(
        "User", back_populates="assigned_assets",
        foreign_keys=[assigned_to_id],
    )
    history = relationship(
        "AssetHistory", back_populates="asset",
        foreign_keys="AssetHistory.asset_id",
        cascade="all, delete-orphan",
    )



class License(Base):
    __tablename__ = "licenses"

    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_INACTIVE = "inactive"

    STATUS_CHOICES = [
        ("active", "Aktywna"),
        ("expired", "Wygasła"),
        ("inactive", "Nieaktywna"),
    ]

    id = Column(Integer, primary_key=True)
    asset_tag = Column(String(12), unique=True, nullable=False, index=True)
    tag_number = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    vendor = Column(String(100), default="")
    license_key = Column(String(500), default="")
    seats = Column(Integer, default=1)
    purchase_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    purchase_price = Column(Numeric(10, 2), nullable=True)
    status = Column(String(20), default="active", index=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assigned_users = relationship(
        "User", secondary=license_users, back_populates="licenses",
    )
    history = relationship(
        "AssetHistory", back_populates="license",
        foreign_keys="AssetHistory.license_id",
        cascade="all, delete-orphan",
    )

    @property
    def seats_used(self) -> int:
        return len(self.assigned_users)


class AssetHistory(Base):
    __tablename__ = "asset_history"

    ACTION_ASSIGN = "assign"
    ACTION_RETURN = "return"
    ACTION_MAINTENANCE = "maintenance"
    ACTION_NOTE = "note"
    ACTION_STATUS = "status"

    ACTION_CHOICES = [
        ("assign", "Przypisanie"),
        ("return", "Zwrot"),
        ("maintenance", "Serwis"),
        ("note", "Notatka"),
        ("status", "Zmiana statusu"),
    ]

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=True)
    license_id = Column(Integer, ForeignKey("licenses.id", ondelete="CASCADE"), nullable=True)
    action = Column(String(20), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    performed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    asset = relationship("Asset", back_populates="history", foreign_keys=[asset_id])
    license = relationship("License", back_populates="history", foreign_keys=[license_id])
    user = relationship("User", foreign_keys=[user_id])
    performed_by = relationship("User", foreign_keys=[performed_by_id])

