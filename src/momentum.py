
"""Deterministic relative momentum scoring for Shift11."""

from typing import Any

from src.analytics import attacking_direction


WINDOW_SECONDS = 300

WEIGHTS = {
    "territory": 0.20,
    "progression": 0.25,
    "pressure": 0.20,
    "chance_creation": 0.25,
    "possession_control": 0.10,
}

ON_BALL_EVENTS = {"pass", "carry", "cross", "shot"}
PROGRESSION_EVENTS = {"pass", "carry"}
DEFENSIVE_EVENTS = {"pressure", "tackle", "interception", "recovery"}
FINAL_THIRD_X = 66.67
PITCH_LENGTH = 100.0


def attacking_x(match: dict[str, Any], event: dict[str, Any]) -> float:
    """Convert world x into the event team's attacking direction."""
    direction = attacking_direction(
        match, event["team_id"], event["period"]
    )
    x = float(event["x"])
    return x if direction == 1 else PITCH_LENGTH - x


def attacking_end_x(match: dict[str, Any], event: dict[str, Any]) -> float:
    """Convert the event's end x-coordinate into attacking direction."""
    direction = attacking_direction(
        match, event["team_id"], event["period"]
    )
    x_end = float(event["x_end"])
    return x_end if direction == 1 else PITCH_LENGTH - x_end


def relative_share(home_value: float, away_value: float) -> tuple[float, float]:
    """Convert two non-negative values into shares totalling 100."""
    home_value = max(0.0, home_value)
    away_value = max(0.0, away_value)
    total = home_value + away_value

    if total == 0:
        return 50.0, 50.0

    return (
        100.0 * home_value / total,
        100.0 * away_value / total,
    )


def calculate_momentum_scores(
    match_data: dict[str, Any],
    end_time: int,
    window_seconds: int = WINDOW_SECONDS,
) -> dict[str, Any]:
    """Calculate transparent, relative 0-100 momentum scores.

    The two teams' scores sum to 100. A score of 50 represents
    parity relative to the other team in this window.
    """
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")

    match = match_data["match"]
    home_id = match["home_team_id"]
    away_id = match["away_team_id"]
    start_time = end_time - window_seconds

    events = [
        event for event in match_data["events"]
        if start_time < event["timestamp_seconds"] <= end_time
        and event["team_id"] in {home_id, away_id}
    ]
    if not events:
        return {
            "timestamp_seconds": end_time,
            "window_seconds": window_seconds,
            "scores": {home_id: 50.0, away_id: 50.0},
            "components": {
            home_id: {name: 50.0 for name in WEIGHTS},
            away_id: {name: 50.0 for name in WEIGHTS},
        },
        "raw_metrics": {
            home_id: {name: 0.0 for name in WEIGHTS},
            away_id: {name: 0.0 for name in WEIGHTS},
        },
        "weights": WEIGHTS.copy(),
    }

    raw = {
        team_id: {
            "territory_positions": [],
            "progression_metres": 0.0,
            "final_third_entries": 0,
            "pressure_actions": 0,
            "successful_defensive_actions": 0,
            "shots": 0,
            "crosses": 0,
            "possession_ids": set(),
        }
        for team_id in (home_id, away_id)
    }

    for event in events:
        team_id = event["team_id"]
        event_type = event["event_type"]
        values = raw[team_id]

        # Count possession IDs by declared possession owner, not
        # by the team performing a defensive action.
        possession_owner = event.get("possession_team_id")
        possession_id = event.get("possession_id")
        if possession_owner == team_id and possession_id is not None:
            values["possession_ids"].add(possession_id)

        if event_type in ON_BALL_EVENTS:
            start_x = attacking_x(match, event)
            values["territory_positions"].append(start_x)

            if event_type == "shot":
                values["shots"] += 1

            if event_type == "cross":
                values["crosses"] += 1

            if (
                event_type in PROGRESSION_EVENTS
                and event.get("success") is True
                and event.get("x_end") is not None
            ):
                end_x = attacking_end_x(match, event)
                values["progression_metres"] += end_x - start_x

                # Count an entry only when the action crosses
                # the final-third boundary, not every event inside it.
                if start_x < FINAL_THIRD_X <= end_x:
                    values["final_third_entries"] += 1

        if event_type in DEFENSIVE_EVENTS:
            values["pressure_actions"] += 1
            if event.get("success") is True:
                values["successful_defensive_actions"] += 1

    # Build interpretable raw component values.
    components_raw = {}
    for team_id, values in raw.items():
        positions = values["territory_positions"]

        components_raw[team_id] = {
            "territory": (
                sum(positions) / len(positions) if positions else 0.0
            ),
            "progression": (
                max(0.0, values["progression_metres"])
                + 5.0 * values["final_third_entries"]
            ),
            "pressure": (
                values["successful_defensive_actions"]
                + 0.25 * values["pressure_actions"]
            ),
            # These are proxies, not expected-goals or shot-quality metrics.
            "chance_creation": (
                3.0 * values["shots"] + values["crosses"]
            ),
            "possession_control": float(len(values["possession_ids"])),
        }

    # Convert each component into a relative share between the teams.
    home_components = {}
    away_components = {}

    for component in WEIGHTS:
        home_share, away_share = relative_share(
            components_raw[home_id][component],
            components_raw[away_id][component],
        )
        home_components[component] = home_share
        away_components[component] = away_share

    home_score = sum(
        home_components[name] * weight
        for name, weight in WEIGHTS.items()
    )
    away_score = sum(
        away_components[name] * weight
        for name, weight in WEIGHTS.items()
    )

    return {
        "timestamp_seconds": end_time,
        "window_seconds": window_seconds,
        "scores": {
            home_id: round(home_score, 2),
            away_id: round(away_score, 2),
        },
        "components": {
            home_id: {
                name: round(value, 2)
                for name, value in home_components.items()
            },
            away_id: {
                name: round(value, 2)
                for name, value in away_components.items()
            },
        },
        "raw_metrics": components_raw,
        "weights": WEIGHTS.copy(),
    }


def generate_momentum_series(
    match_data: dict[str, Any],
    window_seconds: int = WINDOW_SECONDS,
    interval_seconds: int = 30,
) -> list[dict[str, Any]]:
    """Calculate momentum scores at regular match-time intervals."""
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")

    duration = int(
        match_data["match"].get(
            "duration_seconds",
            match_data.get("metadata", {}).get(
                "duration_seconds", 90 * 60
            ),
        )
    )

    return [
        calculate_momentum_scores(
            match_data,
            end_time=end_time,
            window_seconds=window_seconds,
        )
        for end_time in range(interval_seconds, duration + 1, interval_seconds)
    ]
