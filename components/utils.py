"""
utils.py

Shared helper functions used by the Streamlit UI.

This module should never contain Streamlit rendering,
database access, prediction logic, or business logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo


def _format_date(raw: str) -> str:
    """
    Convert a UTC datetime string into Eastern Time
    for display in the UI.
    """

    try:

        utc_dt = (
            datetime.fromisoformat(str(raw).replace("Z", ""))
            .replace(tzinfo=ZoneInfo("UTC"))
        )

        et_dt = utc_dt.astimezone(
            ZoneInfo("America/Toronto")
        )

        return et_dt.strftime("%a %d %b  •  %I:%M %p ET")

    except Exception:

        return str(raw)


def _format_stage(
    stage: Optional[str],
    group: Optional[str],
) -> str:
    """
    Convert database stage names into a
    human-readable label.
    """

    if not stage:
        return ""

    label = stage.replace("_", " ").title()

    if group:

        label = f"{group}  ·  {label}"

    return label


def format_percentage(value: float) -> str:
    """
    Format probabilities for display.
    """

    return f"{value:.1f}%"


def format_expected_goals(value: float) -> str:
    """
    Format expected goals.
    """

    return f"{value:.2f}"


def format_rating(value: float) -> str:
    """
    Format ratings consistently.
    """

    return f"{value:.2f}x"