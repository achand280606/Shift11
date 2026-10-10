"""Deterministic match-state metrics for Shift11.

All coordinates use the shared 0..100 pitch frame.
These functions calculate descriptive metrics only; they do not
declare momentum shifts or generate AI explanations.
"""

from collections import defaultdict
from typing import Any


WINDOW_SECONDS = 300
UPDATE_INTERVAL_SECONDS = 30
PITCH_LENGTH = 100.0


def attacking_direction(
    match: dict[str, Any],
    team_id: str,
    period: int,
) -> int:
    """Return +1 when a team attacks toward increasing world x, else -1."""
    home_positive_first_half = match.get(
        "home_attacks_positive_x_first_half", True
    )

    home_positive = home_positive_first_half if period == 1 else not home_positive_first_half

    if team_id == match["home_team_id"]:
        return 1 if home_positive else -1

    return -1 if home_positive else 1


def attacking_x(
    match: dict[str, Any],
    event: dict[str, Any],
) -> float:
    """Convert world x into the event team's attacking-frame coordinate."""
    direction = attacking_direction(
        match,
        event["team_id"],
        event["period"],
    )
    x = float(event["x"])
    return x if direction == 1 else PITCH_LENGTH - x


def calculate_window_metrics(
    match_data: dict[str, Any],
    end_time: int,
    window_seconds: int = WINDOW_SECONDS,
) -> dict[str, dict[str, float]]:
    """Calculate transparent team metrics over (end_time-window, end_time].

    Returned metrics are raw measurements, not calibrated momentum scores.
    Defensive actions are attributed to the team performing the action.
    """
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")

    match = match_data["match"]
    teams = match_data["teams"]
    events = match_data["events"]

    start_time = end_time - window_seconds
    window_events = [
        event for event in events
        if start_time < event["timestamp_seconds"] <= end_time
    ]

    metrics = {
        team["team_id"]: {
            "event_count": 0.0,
            "territory_sum": 0.0,
            "progression_sum": 0.0,
            "progression_actions": 0.0,
            "pressure_actions": 0.0,
            "successful_defensive_actions": 0.0,
            "shots": 0.0,
            "crosses": 0.0,
            "final_third_entries": 0.0,
            "possession_events": 0.0,
        }
        for team in teams
    }

    for event in window_events:
        team_id = event["team_id"]
        if team_id not in metrics:
            continue

        values = metrics[team_id]
        event_type = event["event_type"]
        values["event_count"] += 1.0
        values["possession_events"] += 1.0

        x_attack = attacking_x(match, event)
        values["territory_sum"] += x_attack

        # Count entries into the attacking final third.
        if x_attack >= 66.67:
            values["final_third_entries"] += 1.0

        # Progression is measured only for successful on-ball movement.
        if (
            event_type in {"pass", "carry"}
            and event.get("success") is True
            and event.get("x_end") is not None
        ):
            end_x = float(event["x_end"])
            direction = attacking_direction(
                match, team_id, event["period"]
            )
            end_x_attack = (
                end_x if direction == 1 else PITCH_LENGTH - end_x
            )
            values["progression_sum"] += end_x_attack - x_attack
            values["progression_actions"] += 1.0

        if event_type in {"pressure", "tackle", "interception", "recovery"}:
            values["pressure_actions"] += 1.0
            if event.get("success") is True:
                values["successful_defensive_actions"] += 1.0

        if event_type == "shot":
            values["shots"] += 1.0

        if event_type == "cross":
            values["crosses"] += 1.0

    # Convert accumulated totals into interpretable averages and rates.
    for values in metrics.values():
        event_count = values["event_count"]
        progression_actions = values["progression_actions"]

        values["mean_attacking_x"] = (
            values["territory_sum"] / event_count if event_count else 0.0
        )
        values["mean_progression"] = (
            values["progression_sum"] / progression_actions
            if progression_actions else 0.0
        )
        values["defensive_success_rate"] = (
            values["successful_defensive_actions"]
            / values["pressure_actions"]
            if values["pressure_actions"] else 0.0
        )

        del values["territory_sum"]
        del values["progression_sum"]

    return metrics


def generate_metric_series(
    match_data: dict[str, Any],
    window_seconds: int = WINDOW_SECONDS,
    interval_seconds: int = UPDATE_INTERVAL_SECONDS,
) -> list[dict[str, Any]]:
    """Calculate rolling metrics at regular intervals throughout the match."""
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")

    duration = int(
        match_data["match"].get(
            "duration_seconds",
            match_data.get("metadata", {}).get("duration_seconds", 90 * 60),
        )
    )

    series = []
    for end_time in range(interval_seconds, duration + 1, interval_seconds):
        series.append({
            "timestamp_seconds": end_time,
            "metrics": calculate_window_metrics(
                match_data,
                end_time=end_time,
                window_seconds=window_seconds,
            ),
        })

    return series
