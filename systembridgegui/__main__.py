"""Main."""
from __future__ import annotations

import asyncio
import json
import sys

from systembridgeshared.logger import setup_logger
from systembridgeshared.settings import Settings
from typer import Typer

from . import Application

asyncio.set_event_loop(asyncio.new_event_loop())

app = Typer()
settings = Settings()

setup_logger(settings.data.log_level, "system-bridge-gui")


@app.command(name="main", help="Run the main application")
def main() -> None:
    """Run the main application."""
    Application(
        settings,
        command="main",
    )


@app.command(name="media-player", help="Run the media player")
def media_player(
    media_type: str,
    data: str,
) -> None:
    """Run the media player."""
    Application(
        settings,
        command=f"media-player-{media_type}",
        data=json.loads(data),
    )


@app.command(name="notification", help="Show a notification")
def notification(
    data: str,
) -> None:
    """Show a notification."""
    Application(
        settings,
        command="notification",
        data=json.loads(data),
    )


if __name__ == "__main__":
    # If no arguments are passed, run the main application.
    if sys.argv[1:] == []:
        main()
    else:
        app()
