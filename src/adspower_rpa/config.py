"""Configuration helpers for AdsPower RPA project."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

import yaml
from pydantic import BaseModel, Field, HttpUrl, PositiveInt, validator


class AdsPowerSettings(BaseModel):
    """Connection settings for the AdsPower local API."""

    base_url: HttpUrl = Field(
        default="http://local.adspower.net:50325",
        description="Base URL of the AdsPower local API service.",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Optional API key for the AdsPower local API (if enabled).",
    )
    timeout_seconds: float = Field(
        default=30.0,
        gt=0.0,
        description="Default timeout for AdsPower API requests.",
    )


class ServiceSelectors(BaseModel):
    """Selectors used to identify authorization state and user info."""

    login_indicators: List[str] = Field(
        default_factory=list,
        description="Selectors whose presence indicates an authenticated session.",
    )
    logout_indicators: List[str] = Field(
        default_factory=list,
        description="Selectors whose presence indicates a logged-out state.",
    )
    display_name: List[str] = Field(
        default_factory=list,
        description="Selectors to extract the user's display name or nickname.",
    )


class ServiceConfig(BaseModel):
    """Configuration describing the target service to verify."""

    name: str = Field(..., description="Human friendly name of the service.")
    target_url: HttpUrl = Field(
        ...,
        description="URL that should be opened to validate the authorization state.",
    )
    selectors: ServiceSelectors = Field(
        default_factory=ServiceSelectors,
        description="CSS selectors used by the automation script.",
    )
    login_path_blocklist: List[str] = Field(
        default_factory=list,
        description="URL path fragments that signal a login page (treated as not authorized).",
    )


class ProfileConfig(BaseModel):
    """Single AdsPower profile to validate."""

    id: str = Field(..., description="AdsPower profile serial or identifier.")
    label: Optional[str] = Field(
        default=None,
        description="Optional human readable label for reports.",
    )

    @validator("id")
    def _strip_id(cls, value: str) -> str:  # pylint: disable=no-self-argument
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("profile id cannot be empty")
        return cleaned


class ProjectConfig(BaseModel):
    """Top-level configuration for the AdsPower authorization checker."""

    adspower: AdsPowerSettings = Field(default_factory=AdsPowerSettings)
    service: ServiceConfig
    profiles: List[ProfileConfig] = Field(
        ...,
        min_items=1,
        description="List of AdsPower profiles to validate.",
    )
    concurrency: PositiveInt = Field(
        default=3,
        description="Maximum number of concurrent profile checks.",
    )


def load_config(path: Path | str) -> ProjectConfig:
    """Load and validate project configuration from a YAML or JSON file."""

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as handle:
        raw: Any = yaml.safe_load(handle)

    if not isinstance(raw, dict):
        raise ValueError("Configuration root must be a mapping/dictionary")

    return ProjectConfig.parse_obj(raw)


__all__ = [
    "AdsPowerSettings",
    "ServiceSelectors",
    "ServiceConfig",
    "ProfileConfig",
    "ProjectConfig",
    "load_config",
]
