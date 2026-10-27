"""Secure authentication helpers for the utility tracker.

No new dependencies: passwords use stdlib PBKDF2-HMAC-SHA256, sessions use
opaque random tokens whose SHA-256 hash is stored (the raw token is shown
only once, at login). Sessions live in the database so they work across
Vercel serverless instances.
"""

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

import models
from database import get_db

ROLES = ("customer", "partner", "super_admin")
STAFF_ROLES = ("partner", "super_admin")

SESSION_DAYS = 7
PBKDF2_ITERATIONS = 200_000

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

bearer = HTTPBearer(auto_error=False)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match((email or "").strip()))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _name, iterations, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def create_session(db: Session, user: models.User) -> str:
    """Create a session and return the raw token (shown only once)."""
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db.add(
        models.Session(
            token_hash=token_hash,
            user_id=user.id,
            expires_at=now_utc() + timedelta(days=SESSION_DAYS),
        )
    )
    db.commit()
    return token


def destroy_session(db: Session, token: str) -> None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db.query(models.Session).filter(models.Session.token_hash == token_hash).delete()
    db.commit()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required.")
    token_hash = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
    session = (
        db.query(models.Session)
        .filter(
            models.Session.token_hash == token_hash,
            models.Session.expires_at > now_utc(),
        )
        .first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please log in again.",
        )
    user = session.user
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive. Contact your administrator.",
        )
    return user


def require_roles(*roles: str):
    """Dependency factory: only the given roles may use the endpoint."""

    def checker(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role cannot access this.",
            )
        return user

    return checker


require_staff = require_roles(*STAFF_ROLES)
require_admin = require_roles("super_admin")
require_customer = require_roles("customer")


def get_customer_profile_or_404(db: Session, user: models.User) -> models.CustomerProfile:
    profile = (
        db.query(models.CustomerProfile)
        .filter(models.CustomerProfile.user_id == user.id)
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Customer profile not found.")
    return profile


def customer_payment_status(prop: models.Property | None) -> str:
    """Derived customer-level status, always in sync with the ledger.

    UNLINKED when no home is linked yet, UNPAID when any amount is pending,
    PAID otherwise. Staff change it only by updating bill entries, never by
    editing this value directly, so it cannot drift from the ledger.
    """
    if prop is None:
        return "UNLINKED"
    pending = max(0.0, prop.cumulative_billed_amount - prop.cumulative_paid_amount)
    return "UNPAID" if pending > 0 else "PAID"
