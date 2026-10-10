"""Structural and sequence validation for Shift11 generated match JSON.

This module deliberately validates the synthetic event evidence, not whether a
momentum shift occurred. Momentum classification belongs to the analytics layer.
"""

import argparse
import json
import math
from pathlib import Path
from typing import Any

HALF_TIME_SECONDS = 45 * 60
COORD_MIN = 0.0
COORD_MAX = 100.0
COORD_TOLERANCE = 0.15
BALL_ACTIONS = {"pass", "carry", "cross", "shot"}
DEFENSIVE_ACTIONS = {"pressure", "tackle", "interception"}


def validate_match_data(data: dict[str, Any]) -> list[str]:
    """Return validation problems; an empty list means the data passed checks."""
    errors: list[str] = []

    def error(message: str) -> None:
        # Keep terminal output readable even for a seriously malformed file.
        if len(errors) < 100:
            errors.append(message)

    if not isinstance(data, dict):
        return ["Match data must be a JSON object."]

    match = data.get("match")
    teams = data.get("teams")
    players = data.get("players")
    events = data.get("events")

    if not isinstance(match, dict):
        return ["Missing or invalid 'match' object."]
    if not isinstance(teams, list) or not teams:
        return ["Missing or invalid 'teams' list."]
    if not isinstance(players, list) or not players:
        return ["Missing or invalid 'players' list."]
    if not isinstance(events, list) or not events:
        return ["Missing or invalid 'events' list."]

    match_id = match.get("match_id")
    duration = match.get("duration_seconds")
    home_id = match.get("home_team_id")
    away_id = match.get("away_team_id")
    if not isinstance(duration, (int, float)) or duration <= 0:
        return ["match.duration_seconds must be a positive number."]
    if home_id == away_id or home_id is None or away_id is None:
        error("Home and away team IDs must be present and different.")

    team_ids = [team.get("team_id") for team in teams if isinstance(team, dict)]
    if len(team_ids) != len(teams):
        error("Every team entry must be an object with a team_id.")
    if len(team_ids) != len(set(team_ids)):
        error("Team IDs must be unique.")
    valid_team_ids = set(team_ids)
    if home_id not in valid_team_ids or away_id not in valid_team_ids:
        error("Match home_team_id and away_team_id must reference listed teams.")

    player_by_id: dict[str, dict[str, Any]] = {}
    for index, player in enumerate(players):
        if not isinstance(player, dict):
            error(f"Player entry {index} is not an object.")
            continue
        player_id = player.get("player_id")
        if not player_id:
            error(f"Player entry {index} is missing player_id.")
            continue
        if player_id in player_by_id:
            error(f"Duplicate player_id: {player_id}.")
        player_by_id[player_id] = player
        if player.get("team_id") not in valid_team_ids:
            error(f"Player {player_id} references unknown team_id.")

    event_ids: set[str] = set()
    possession_owners: dict[str, str] = {}
    possession_periods: dict[str, int] = {}
    closed_possessions: set[str] = set()
    current_possession: str | None = None
    expected_ball_point: tuple[float, float] | None = None
    previous_timestamp = -1.0
    previous_period_by_possession: dict[str, int] = {}

    for index, event in enumerate(events):
        if not isinstance(event, dict):
            error(f"Event entry {index} is not an object.")
            continue

        event_id = event.get("event_id")
        if not event_id:
            error(f"Event entry {index} is missing event_id.")
        elif event_id in event_ids:
            error(f"Duplicate event_id: {event_id}.")
        else:
            event_ids.add(event_id)

        if event.get("match_id") != match_id:
            error(f"Event {event_id} references the wrong match_id.")

        timestamp = event.get("timestamp_seconds")
        if not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
            error(f"Event {event_id} has an invalid timestamp.")
            timestamp = previous_timestamp
        else:
            if timestamp < 0 or timestamp >= duration:
                error(f"Event {event_id} timestamp is outside match duration.")
            if timestamp < previous_timestamp:
                error(f"Events are not chronologically ordered at {event_id}.")
            previous_timestamp = timestamp

        expected_period = 1 if timestamp < HALF_TIME_SECONDS else 2
        period = event.get("period")
        if period != expected_period:
            error(f"Event {event_id} has period {period}, inconsistent with its timestamp.")

        team_id = event.get("team_id")
        if team_id not in valid_team_ids:
            error(f"Event {event_id} references unknown team_id {team_id}.")

        player_id = event.get("player_id")
        actor = player_by_id.get(player_id)
        if actor is None:
            error(f"Event {event_id} references unknown player_id {player_id}.")
        elif actor.get("team_id") != team_id:
            error(f"Event {event_id}: player {player_id} does not belong to event team {team_id}.")

        receiver_id = event.get("receiver_player_id")
        if receiver_id is not None:
            receiver = player_by_id.get(receiver_id)
            if receiver is None:
                error(f"Event {event_id} references unknown receiver_player_id {receiver_id}.")
            elif receiver.get("team_id") != team_id:
                error(f"Event {event_id}: receiver {receiver_id} is not on the passing player's team.")
        if event.get("event_type") == "pass" and event.get("success") is True and receiver_id is None:
            error(f"Successful pass {event_id} is missing receiver_player_id.")

        start_values = (event.get("x"), event.get("y"))
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in start_values):
            error(f"Event {event_id} has invalid start coordinates.")
            start_point = None
        else:
            start_point = (float(start_values[0]), float(start_values[1]))
            if any(v < COORD_MIN or v > COORD_MAX for v in start_point):
                error(f"Event {event_id} start coordinates are outside 0..100.")

        end_x, end_y = event.get("x_end"), event.get("y_end")
        if (end_x is None) != (end_y is None):
            error(f"Event {event_id} must provide both x_end and y_end, or neither.")
        elif end_x is not None:
            if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (end_x, end_y)):
                error(f"Event {event_id} has invalid end coordinates.")
            elif not (COORD_MIN <= end_x <= COORD_MAX and COORD_MIN <= end_y <= COORD_MAX):
                error(f"Event {event_id} end coordinates are outside 0..100.")

        possession_id = event.get("possession_id")
        owner = event.get("possession_team_id")
        if not possession_id:
            error(f"Event {event_id} is missing possession_id.")
        if owner not in valid_team_ids:
            error(f"Event {event_id} has an unknown possession_team_id.")

        if possession_id:
            if possession_id in possession_owners and possession_owners[possession_id] != owner:
                error(f"Possession {possession_id} has more than one declared owner.")
            else:
                possession_owners[possession_id] = owner

            if possession_id in possession_periods and possession_periods[possession_id] != period:
                error(f"Possession {possession_id} crosses a match period.")
            else:
                possession_periods[possession_id] = period

            if possession_id != current_possession:
                if possession_id in closed_possessions:
                    error(f"Possession ID {possession_id} reappears after another possession started.")
                if current_possession is not None:
                    closed_possessions.add(current_possession)
                current_possession = possession_id
                expected_ball_point = None

            # Defensive actions can be performed by the opposing team while the
            # possession owner is still the team that had the ball before outcome.
            # Non-defensive on-ball actions should belong to the declared owner.
            if event.get("event_type") not in DEFENSIVE_ACTIONS and owner is not None and team_id != owner:
                error(f"Event {event_id}: on-ball action team differs from possession owner.")

        # Within one possession, each event should begin at the last recorded ball
        # endpoint. Defensive pressure/tackle/interception events share that point.
        if start_point is not None and expected_ball_point is not None:
            gap = math.dist(start_point, expected_ball_point)
            if gap > COORD_TOLERANCE:
                error(
                    f"Event {event_id} starts {gap:.2f} coordinate units from the previous "
                    "ball endpoint in the same possession."
                )

        if end_x is not None and end_y is not None and isinstance(end_x, (int, float)) and isinstance(end_y, (int, float)):
            expected_ball_point = (float(end_x), float(end_y))

        if possession_id:
            previous_period_by_possession[possession_id] = period

    # A completed successful pass should be followed by the named receiver's next
    # on-ball action, unless an opposing defensive event successfully wins the ball
    # first or the possession is explicitly ended.
    events_by_possession: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        if isinstance(event, dict) and event.get("possession_id"):
            events_by_possession.setdefault(event["possession_id"], []).append(event)

    for possession_id, sequence in events_by_possession.items():
        owner = possession_owners.get(possession_id)
        for i, event in enumerate(sequence):
            if event.get("event_type") != "pass" or event.get("success") is not True:
                continue
            receiver_id = event.get("receiver_player_id")
            if not receiver_id:
                continue
            for later in sequence[i + 1:]:
                if (later.get("event_type") in DEFENSIVE_ACTIONS
                        and later.get("team_id") != owner and later.get("success") is True):
                    break  # Defender won possession before the receiver's next action.
                if later.get("event_type") == "turnover":
                    break  # Possession was explicitly ended.
                if later.get("event_type") in BALL_ACTIONS:
                    if later.get("team_id") == owner and later.get("player_id") != receiver_id:
                        error(
                            f"Successful pass {event.get('event_id')} names receiver {receiver_id}, "
                            f"but next on-ball action in possession {possession_id} is by "
                            f"{later.get('player_id')}."
                        )
                    break

    if len(errors) >= 100:
        errors.append("Further validation errors omitted after the first 100.")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a generated Shift11 match JSON file.")
    parser.add_argument("file", nargs="?", default="data/match_001.json", help="Path to match JSON")
    args = parser.parse_args()
    path = Path(args.file)
    if not path.is_file():
        parser.error(f"file does not exist: {path}")
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    errors = validate_match_data(data)
    if errors:
        print(f"Match validation FAILED: {len(errors)} issue(s) found.")
        for message in errors:
            print(f"- {message}")
        raise SystemExit(1)

    possession_count = len({event["possession_id"] for event in data["events"]})
    print("Match validation passed.")
    print(f"Events: {len(data['events'])}")
    print(f"Possessions: {possession_count}")
    print("Checked: references, time/period, coordinates, possession ownership, spatial continuity, and successful-pass receivers.")


if __name__ == "__main__":
    main()
