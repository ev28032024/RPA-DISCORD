"""Async client for interacting with the AdsPower local API."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import httpx


class AdsPowerClient:
    """Wrapper around the AdsPower local API."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        async with self._lock:
            if self._client is None:
                headers = {"Content-Type": "application/json"}
                if self._api_key:
                    headers["Authorization"] = f"Bearer {self._api_key}"
                self._client = httpx.AsyncClient(
                    base_url=self._base_url,
                    headers=headers,
                    timeout=self._timeout,
                )
            return self._client

    async def close(self) -> None:
        """Dispose the underlying HTTP client."""

        async with self._lock:
            if self._client is not None:
                await self._client.aclose()
                self._client = None

    async def run_automation(self, profile_id: str, steps: list[dict[str, Any]]) -> Dict[str, Any]:
        """Execute an automation scenario for a single profile.

        Parameters
        ----------
        profile_id:
            Serial or identifier of the AdsPower profile.
        steps:
            Automation steps describing the RPA workflow to run.
        """

        client = await self._get_client()
        payload: Dict[str, Any] = {
            "profile_id": profile_id,
            "steps": steps,
            "options": {
                "fail_on_selector_timeout": True,
                "capture_console": True,
            },
        }

        response = await client.post("/api/v1/automation/run", json=payload)
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
        return data

    async def __aenter__(self) -> "AdsPowerClient":
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.close()


__all__ = ["AdsPowerClient"]
