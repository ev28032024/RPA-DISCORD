"""Data models describing the outcome of authorization checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(slots=True)
class AuthorizationDetails:
    """Detailed information extracted from a service page."""

    authorized: bool
    display_name: Optional[str]
    profile_serial: Optional[str]
    raw_variables: Dict[str, Any]


@dataclass(slots=True)
class ProfileCheckResult:
    """Result of running the authorization check on a profile."""

    profile_id: str
    label: Optional[str]
    success: bool
    details: Optional[AuthorizationDetails]
    error: Optional[str]
    started_at: datetime
    finished_at: datetime
    raw_response: Dict[str, Any]


def now_utc() -> datetime:
    """Return the current UTC timestamp with timezone info."""

    return datetime.now(timezone.utc)


__all__ = ["AuthorizationDetails", "ProfileCheckResult", "now_utc"]
