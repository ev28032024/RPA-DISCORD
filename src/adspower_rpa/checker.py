"""High level orchestration of AdsPower authorization checks."""

from __future__ import annotations

import asyncio
from typing import Iterable, List

from .client import AdsPowerClient
from .config import ProfileConfig, ProjectConfig
from .models import AuthorizationDetails, ProfileCheckResult, now_utc
from .scenarios import DiscordAuthorizationScenario


class AuthorizationChecker:
    """Coordinates AdsPower automation runs across multiple profiles."""

    def __init__(
        self,
        client: AdsPowerClient,
        scenario: DiscordAuthorizationScenario,
        profiles: Iterable[ProfileConfig],
        concurrency: int = 3,
    ) -> None:
        self._client = client
        self._scenario = scenario
        self._profiles = list(profiles)
        self._concurrency = max(1, concurrency)

    @classmethod
    def from_config(
        cls,
        client: AdsPowerClient,
        config: ProjectConfig,
        scenario: DiscordAuthorizationScenario,
    ) -> "AuthorizationChecker":
        return cls(
            client=client,
            scenario=scenario,
            profiles=config.profiles,
            concurrency=config.concurrency,
        )

    async def run(self) -> List[ProfileCheckResult]:
        """Run the authorization scenario for all configured profiles."""

        semaphore = asyncio.Semaphore(self._concurrency)
        tasks = [
            asyncio.create_task(self._run_single(profile, semaphore))
            for profile in self._profiles
        ]
        results = await asyncio.gather(*tasks)
        return results

    async def _run_single(
        self, profile: ProfileConfig, semaphore: asyncio.Semaphore
    ) -> ProfileCheckResult:
        started_at = now_utc()
        raw_response = {}
        error: str | None = None
        details: AuthorizationDetails | None = None
        success = False
        async with semaphore:
            try:
                raw_response = await self._client.run_automation(
                    profile_id=profile.id,
                    steps=self._scenario.to_payload(),
                )
                variables = _extract_variables(raw_response)
                details = AuthorizationDetails(
                    authorized=_parse_bool(variables.get("service_authorized")),
                    display_name=_coerce_optional_str(variables.get("service_display_name")),
                    profile_serial=_coerce_optional_str(variables.get("profile_serial")),
                    raw_variables=variables,
                )
                success = True
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
        finished_at = now_utc()
        return ProfileCheckResult(
            profile_id=profile.id,
            label=profile.label,
            success=success,
            details=details,
            error=error,
            started_at=started_at,
            finished_at=finished_at,
            raw_response=raw_response,
        )


def _extract_variables(response: dict) -> dict:
    """Extract variables dictionary from AdsPower automation response."""

    variables = response.get("data", {}).get("variables")
    if isinstance(variables, dict):
        return variables
    if isinstance(response.get("variables"), dict):
        return response["variables"]
    return {}


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _coerce_optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = ["AuthorizationChecker"]
