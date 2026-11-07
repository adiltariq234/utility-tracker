from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)


# ---------- Property ----------
# NOTE: Block / address_block was removed everywhere user-visible (2026-11-01).
# The legacy column still exists in old databases and is ignored, never returned.
class PropertyCreate(BaseModel):
    property_id: str = Field(..., min_length=1)
    owner_name: Optional[str] = "Unassigned"
    initial_units: float = Field(default=0.0, ge=0)
    initial_meter_reading: float = Field(default=0.0, ge=0)


class BulkPropertyCreate(BaseModel):
    prefix: str = "HOME-"
    start_number: int = Field(default=1, ge=1)
    count: int = Field(default=100, ge=1, le=1000)


class PropertyUpdate(BaseModel):
    owner_name: Optional[str] = None


class PropertyRename(BaseModel):
    new_property_id: str = Field(..., min_length=1)


# ---------- Usage ----------
class UsageEntryCreate(BaseModel):
    property_id: str = Field(..., min_length=1)
    billing_period: str = Field(..., min_length=1)
    # Manually typed previous meter reading (v4.4). When given, units are
    # current_reading - previous_reading. When omitted, the home's last
    # meter reading (previous bill's current reading) is used, as before.
    previous_reading: Optional[float] = Field(default=None, ge=0)
    current_reading: Optional[float] = Field(default=None, ge=0)
    added_units: Optional[float] = Field(default=None, gt=0)
    bill_amount: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def check_reading_or_units(self):
        if self.current_reading is None and self.added_units is None:
            raise ValueError("Current meter reading ya added units mein se koi ek dena zaroori hai.")
        if self.previous_reading is not None and self.current_reading is None:
            raise ValueError("Previous reading sirf current reading ke sath di ja sakti hai.")
        if (
            self.previous_reading is not None
            and self.current_reading is not None
            and self.current_reading <= self.previous_reading
        ):
            raise ValueError("Current reading previous reading se zyada honi chahiye.")
        return self


class UsageEntryUpdate(BaseModel):
    billing_period: Optional[str] = Field(default=None, min_length=1)
    previous_reading: Optional[float] = Field(default=None, ge=0)
    current_reading: Optional[float] = Field(default=None, ge=0)
    added_units: Optional[float] = Field(default=None, gt=0)
    bill_amount: Optional[float] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check_something_to_update(self):
        if all(
            v is None
            for v in (self.billing_period, self.previous_reading, self.current_reading, self.added_units, self.bill_amount)
        ):
            raise ValueError("Update karne ke liye kam az kam ek field dena zaroori hai.")
        if (
            self.previous_reading is not None
            and self.current_reading is not None
            and self.current_reading <= self.previous_reading
        ):
            raise ValueError("Current reading previous reading se zyada honi chahiye.")
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
    # True when previous_reading was typed in by hand (v4.4); False when
    # the chain derived it from the previous bill's current reading.
    previous_reading_manual: bool = False
    bill_amount: float
    payment_status: str = "UNPAID"
    paid_date: Optional[datetime] = None
    entry_date: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Frozen at creation (old bills: derived fallback, see main.enrich_log).
    rate_per_unit: Optional[float] = None
    due_date: Optional[date] = None
    # Live for UNPAID bills; frozen at payment time for PAID bills.
    late_fine: float = 0.0

    @computed_field
    @property
    def total_payable(self) -> float:
        return round(self.bill_amount + (self.late_fine or 0.0), 2)


# ---------- Settings ----------
class FineStage(BaseModel):
    days_after_due: int = Field(..., ge=0)
    amount: float = Field(..., ge=0)


class SettingsUpdate(BaseModel):
    rate_per_unit: float = Field(..., gt=0)
    due_day: int = Field(..., ge=1, le=31)
    fine_stages: List[FineStage] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_stages(self):
        days = [s.days_after_due for s in self.fine_stages]
        if len(days) != len(set(days)):
            raise ValueError("Fine stages ke days_after_due alag-alag hone chahiye.")
        return self


class SettingsResponse(BaseModel):
    rate_per_unit: float
    due_day: int
    fine_stages: List[FineStage]


# ---------- Property responses ----------
class PropertyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    property_id: str
    owner_name: Optional[str] = None
    cumulative_units: float
    cumulative_billed_amount: float
    cumulative_paid_amount: float = 0.0
    last_meter_reading: float = 0.0
    last_updated: Optional[datetime] = None
    # Sum of live fines on this home's UNPAID bills (0 unless enriched).
    total_fine: float = 0.0

    @computed_field
    @property
    def pending_amount(self) -> float:
        return round(max(0.0, self.cumulative_billed_amount - self.cumulative_paid_amount), 2)

    @computed_field
    @property
    def total_payable(self) -> float:
        return round(self.pending_amount + (self.total_fine or 0.0), 2)


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
    total_fine: float = 0.0
    total_payable: float = 0.0


# ---------- Auth, roles, customers (added 2026-10-27) ----------
class UserRegister(BaseModel):
    """Public registration creates a CUSTOMER account only. The role is never
    accepted from a public request, so nobody can self-promote to staff."""

    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = None
    phone: Optional[str] = None
    account_number: str = Field(..., min_length=1, max_length=64)
    home_number: Optional[str] = None


class UserLogin(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class AdminUserCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    role: Literal["customer", "partner", "super_admin"]
    full_name: Optional[str] = None
    phone: Optional[str] = None
    account_number: Optional[str] = None
    home_number: Optional[str] = None


class AdminRoleUpdate(BaseModel):
    role: Literal["customer", "partner", "super_admin"]


class AdminActiveUpdate(BaseModel):
    is_active: bool


class AdminPasswordReset(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class LinkHomeRequest(BaseModel):
    home_number: str = Field(..., min_length=1, max_length=64)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    force_password_change: bool
    created_at: Optional[datetime] = None


class CustomerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_number: str
    home_number: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    user: UserResponse
    profile: Optional[CustomerProfileResponse] = None


class CustomerDashboardResponse(BaseModel):
    user: UserResponse
    profile: CustomerProfileResponse
    property: Optional[PropertyResponse] = None
    logs: List[UsageLogResponse] = []
    payment_status: str
    total_billed: float
    total_paid: float
    total_pending: float


class CustomerListItem(BaseModel):
    user_id: int
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    account_number: str
    home_number: Optional[str] = None
    payment_status: str
    total_billed: float
    total_paid: float
    total_pending: float
