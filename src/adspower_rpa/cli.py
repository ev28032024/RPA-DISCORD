"""Command line interface for the AdsPower RPA authorization checker."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .checker import AuthorizationChecker
from .client import AdsPowerClient
from .config import ProjectConfig, load_config
from .scenarios import build_discord_authorization_scenario

app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def check(
    config_path: Path = typer.Option(
        Path("adspower.yaml"),
        "--config",
        "-c",
        exists=True,
        readable=True,
        resolve_path=True,
        help="Path to the project configuration file.",
    ),
) -> None:
    """Run authorization checks for all profiles described in the configuration file."""

    config = _load_configuration(config_path)
    scenario = build_discord_authorization_scenario(config.service)

    async def _runner() -> None:
        async with AdsPowerClient(
            base_url=str(config.adspower.base_url),
            api_key=config.adspower.api_key,
            timeout_seconds=config.adspower.timeout_seconds,
        ) as client:
            checker = AuthorizationChecker.from_config(client, config, scenario)
            results = await checker.run()
            _render_results(results)

    asyncio.run(_runner())


def _load_configuration(path: Path) -> ProjectConfig:
    try:
        return load_config(path)
    except Exception as exc:  # noqa: BLE001
        raise typer.BadParameter(str(exc)) from exc


def _render_results(results) -> None:
    table = Table(title="AdsPower Authorization Report")
    table.add_column("Profile ID", style="cyan", no_wrap=True)
    table.add_column("Label", style="magenta")
    table.add_column("Authorized", style="green")
    table.add_column("Display name", style="yellow")
    table.add_column("Error", style="red")

    for result in results:
        authorized: Optional[str] = None
        display_name: Optional[str] = None
        if result.details:
            authorized = "Yes" if result.details.authorized else "No"
            display_name = result.details.display_name or ""
        table.add_row(
            result.profile_id,
            result.label or "",
            authorized or ("-" if result.success else "No"),
            display_name or "",
            result.error or "",
        )
    console.print(table)


if __name__ == "__main__":
    app()
