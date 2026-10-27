from sqlalchemy import Boolean, Column, String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class Property(Base):
    __tablename__ = "properties"

    property_id = Column(String, primary_key=True, index=True)  # e.g., HOME-001
    owner_name = Column(String, nullable=True, default="Unassigned")
    address_block = Column(String, nullable=True, default="General")

    # Cumulative totals
    cumulative_units = Column(Float, default=0.0, nullable=False)
    cumulative_billed_amount = Column(Float, default=0.0, nullable=False)
    cumulative_paid_amount = Column(Float, default=0.0, nullable=False)

    # Aakhri meter reading (agli entry ki previous reading yahi banegi)
    last_meter_reading = Column(Float, default=0.0, nullable=False)

    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    logs = relationship("UsageLog", back_populates="property_ref", cascade="all, delete-orphan")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    log_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # onupdate="CASCADE": Home ID rename par Postgres history khud naye ID par move kar deta hai
    property_id = Column(
        String,
        ForeignKey("properties.property_id", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    billing_period = Column(String, nullable=False)  # e.g., "Oct-2026"

    previous_total_units = Column(Float, nullable=False)
    added_units = Column(Float, nullable=False)
    new_total_units = Column(Float, nullable=False)

    previous_reading = Column(Float, nullable=True)
    current_reading = Column(Float, nullable=True)

    bill_amount = Column(Float, default=0.0, nullable=False)
    payment_status = Column(String, default="UNPAID", nullable=False, index=True)  # "PAID" ya "UNPAID"
    paid_date = Column(DateTime, nullable=True)

    entry_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=True)

    property_ref = relationship("Property", back_populates="logs")


# =====================================================================
# Authentication and roles (added 2026-10-27, existing tables untouched)
# Roles: customer, partner, super_admin.
# =====================================================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="customer", index=True)
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    # Set when an admin issues a temporary password: user must change it.
    force_password_change = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    profile = relationship(
        "CustomerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    account_number = Column(String, nullable=False, unique=True, index=True)
    # Home number = Property.property_id. Linked only after verification that
    # the home exists and is not already linked to another customer.
    home_number = Column(
        String,
        ForeignKey("properties.property_id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="profile")
    home = relationship("Property")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # Only the SHA-256 hash of the token is stored; the raw token is shown once at login.
    token_hash = Column(String, nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="sessions")
