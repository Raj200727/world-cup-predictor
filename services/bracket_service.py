"""
bracket_service.py

Builds the tournament bracket from fixture data.
"""

from __future__ import annotations


def build_bracket(fixtures: list[dict]) -> dict[str, list[dict]]:
    """
    Organize fixtures by knockout stage.
    """

    stages = {
        "round_of_32": [],
        "round_of_16": [],
        "quarterfinals": [],
        "semifinals": [],
        "final": [],
        "third_place": [],
    }

    for fixture in fixtures:

        stage = (fixture.get("stage") or "").upper()

        if stage == "ROUND_OF_32":
            stages["round_of_32"].append(fixture)

        elif stage == "ROUND_OF_16":
            stages["round_of_16"].append(fixture)

        elif stage == "QUARTERFINAL":
            stages["quarterfinals"].append(fixture)

        elif stage == "SEMIFINAL":
            stages["semifinals"].append(fixture)

        elif stage == "FINAL":
            stages["final"].append(fixture)

        elif stage == "THIRD_PLACE":
            stages["third_place"].append(fixture)

    return stages

def stage_complete(matches: list[dict]) -> bool:
    """
    Returns True if every match in the stage has finished.
    """

    if not matches:
        return False

    return all(
        match["status"] == "FINISHED"
        for match in matches
    )
def stage_has_started(matches: list[dict]) -> bool:
    """
    Returns True if any match has begun.
    """

    return any(
        match["status"] != "SCHEDULED"
        for match in matches
    )
def stage_has_future_matches(matches: list[dict]) -> bool:
    """
    Returns True if any scheduled matches remain.
    """

    return any(
        match["status"] == "SCHEDULED"
        for match in matches
    )