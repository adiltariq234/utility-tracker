from sqlalchemy import Boolean, Column, Date, String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class Property(Base):
    __tablename__ = "properties"

    property_id = Column(String, primary_key=True, index=True)  # e.g., HOME-001
    owner_name = Column(String, nullable=True, default="Unassigned")
    # LEGACY ONLY: old databases still carry this column. It is never read,
    # never written by new code, and never shown in any API response, bill,
    # printout or export. Data is left untouched so old databases keep working.
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
    # True when the previous reading was typed in by hand on the bill form
    # (v4.4). The chain recalculation then keeps that value instead of
    # re-deriving it from the earlier bill. False = auto-derived from the
    # previous bill's current reading (the pre-v4.4 behaviour for old bills).
    previous_reading_manual = Column(Boolean, default=False, nullable=False)

    bill_amount = Column(Float, default=0.0, nullable=False)
    payment_status = Column(String, default="UNPAID", nullable=False, index=True)  # "PAID" ya "UNPAID"
    paid_date = Column(DateTime, nullable=True)

    # Rate frozen at bill creation (Rs. per unit). Old bills created before
    # this column existed keep a NULL here; responses fall back to the
    # bill-implied rate (bill / units) or the current settings rate.
    rate_per_unit = Column(Float, nullable=True)
    # Due date for this bill, set at creation from the Settings due-day.
    # Old bills keep a NULL here; responses fall back to the due date
    # computed from entry_date + current Settings due-day.
    due_date = Column(Date, nullable=True)
    # Late fine frozen when a bill is marked PAID (so it stops increasing).
    # For UNPAID bills the fine is computed live on every read and this
    # stored value is ignored.
    late_fine = Column(Float, default=0.0, nullable=False)

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


# =====================================================================
# App settings (added 2026-11-01): single row, id = 1.
# - rate_per_unit: fixed Rs. per unit, stored in the DB (never browser-only).
#   Only a super_admin may change it, from Settings. Old bills keep the
#   rate_per_unit frozen on their UsageLog row.
# - due_day: day of month (1-31, clamped to the month's last day) on which
#   each month's bills fall due.
# - fine_stages_json: JSON list of {"days_after_due": int, "amount": float}.
#   The fine for an unpaid bill is the amount of the last stage whose
#   days_after_due has been passed (overdue days > days_after_due).
#   Example default: 1000 from day 1 late, 2000 after 15 days late,
#   3000 after 30 days late. Only a super_admin may change these.
# =====================================================================
class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)
    rate_per_unit = Column(Float, default=50.0, nullable=False)
    due_day = Column(Integer, default=20, nullable=False)
    fine_stages_json = Column(String, nullable=False, default='[{"days_after_due": 0, "amount": 1000}, {"days_after_due": 15, "amount": 2000}, {"days_after_due": 30, "amount": 3000}]')
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# =====================================================================
# Email open tracking (TorqueTalk outreach, added 2026-11-01, free tier).
# Privacy by design: the pixel key (k) contains ONLY a program prefix,
# a lead code and a send date — NEVER an email address, name or IP.
# Example: dal-L1102-20261102, aus-avenue-dental-north-austin-20261102.
# First open per key only (repeat loads are ignored), no IP is stored.
# This table is separate from billing data and is never shown to
# utility-tracker customers; it feeds the outreach daily opens report.
# =====================================================================
class EmailOpen(Base):
    __tablename__ = "email_opens"

    key = Column(String, primary_key=True, index=True)
    program = Column(String, nullable=False, default="")  # dal | aus
    first_opened_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_agent = Column(String, nullable=True, default="")
