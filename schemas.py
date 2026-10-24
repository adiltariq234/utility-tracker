from datetime import datetime
from typing import List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)


# ---------- Property ----------
class PropertyCreate(BaseModel):
    property_id: str = Field(..., min_length=1)
    owner_name: Optional[str] = "Unassigned"
    address_block: Optional[str] = "General"
    initial_units: float = Field(default=0.0, ge=0)
    initial_meter_reading: float = Field(default=0.0, ge=0)


class BulkPropertyCreate(BaseModel):
    prefix: str = "HOME-"
    start_number: int = Field(default=1, ge=1)
    count: int = Field(default=100, ge=1, le=1000)
    address_block: Optional[str] = "Block A"


class PropertyUpdate(BaseModel):
    owner_name: Optional[str] = None
    address_block: Optional[str] = None


class PropertyRename(BaseModel):
    new_property_id: str = Field(..., min_length=1)


# ---------- Usage ----------
class UsageEntryCreate(BaseModel):
    property_id: str = Field(..., min_length=1)
    billing_period: str = Field(..., min_length=1)
    current_reading: Optional[float] = Field(default=None, ge=0)
    added_units: Optional[float] = Field(default=None, gt=0)
    bill_amount: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def check_reading_or_units(self):
        if self.current_reading is None and self.added_units is None:
            raise ValueError("Current meter reading ya added units mein se koi ek dena zaroori hai.")
        return self


class UsageEntryUpdate(BaseModel):
    billing_period: Optional[str] = Field(default=None, min_length=1)
    current_reading: Optional[float] = Field(default=None, ge=0)
    added_units: Optional[float] = Field(default=None, gt=0)
    bill_amount: Optional[float] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check_something_to_update(self):
        if all(
            v is None
            for v in (self.billing_period, self.current_reading, self.added_units, self.bill_amount)
        ):
            raise ValueError("Update karne ke liye kam az kam ek field dena zaroori hai.")
        return self


class PaymentUpdate(BaseModel):
    status: Literal["PAID", "UNPAID"]


class UsageLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: int
    property_id: str
    billing_period: str
    previous_total_units: float
    added_units: float
    new_total_units: float
    previous_reading: Optional[float] = None
    current_reading: Optional[float] = None
    bill_amount: float
    payment_status: str = "UNPAID"
    paid_date: Optional[datetime] = None
    entry_date: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------- Property responses ----------
class PropertyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    property_id: str
    owner_name: Optional[str] = None
    address_block: Optional[str] = None
    cumulative_units: float
    cumulative_billed_amount: float
    cumulative_paid_amount: float = 0.0
    last_meter_reading: float = 0.0
    last_updated: Optional[datetime] = None

    @computed_field
    @property
    def pending_amount(self) -> float:
        return round(max(0.0, self.cumulative_billed_amount - self.cumulative_paid_amount), 2)


class PropertyDetailResponse(PropertyResponse):
    logs: List[UsageLogResponse] = []


# ---------- Dashboard ----------
class DashboardSummary(BaseModel):
    total_homes: int
    active_homes: int
    total_units: float
    total_billed: float
    total_paid: float
    total_pending: float
    unpaid_entries_count: int
