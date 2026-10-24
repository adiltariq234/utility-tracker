from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey
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
