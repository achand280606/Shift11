"""Reproducible synthetic football match generator for Shift11.

Pitch x/y are shared coordinates in the range 0..100. Teams attack in opposite
x directions and switch directions at half-time. Scenario settings influence
events only; they never force a momentum-shift label.
"""

import argparse
import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from src.models import Event, Match, Player, Team

FORMATIONS = {
    "4-3-3": ["GK", "RB", "CB", "CB", "LB", "CM", "CM", "CDM", "RW", "ST", "LW"],
    "4-4-2": ["GK", "RB", "CB", "CB", "LB", "RM", "CM", "CM", "LM", "ST", "ST"],
    "3-5-2": ["GK", "CB", "CB", "CB", "RWB", "CM", "CDM", "CM", "LWB", "ST", "ST"],
    "4-2-3-1": ["GK", "RB", "CB", "CB", "LB", "CDM", "CDM", "RW", "CAM", "LW", "ST"],
}
SCENARIOS = {"balanced", "high_pressing", "counterattack", "defensive_dominance", "harmless_possession"}
HALF_TIME_SECONDS = 45 * 60
DEFAULT_DURATION_SECONDS = 90 * 60

# Positions are expressed in a team's attacking frame (own goal at x=0).
POSITION_ANCHORS = {
    "GK": (5.0, 50.0), "CB": (23.0, 50.0), "RB": (30.0, 79.0), "LB": (30.0, 21.0),
    "RWB": (45.0, 79.0), "LWB": (45.0, 21.0), "CDM": (38.0, 50.0), "CM": (50.0, 50.0),
    "CAM": (62.0, 50.0), "RM": (48.0, 77.0), "LM": (48.0, 23.0), "RW": (70.0, 80.0),
    "LW": (70.0, 20.0), "ST": (78.0, 50.0),
}


def other_team(team_id: str) -> str:
    return "AWAY" if team_id == "HOME" else "HOME"


def create_teams(rng: random.Random, home_formation: Optional[str] = None,
                 away_formation: Optional[str] = None) -> list[Team]:
    names = list(FORMATIONS)
    home_formation = home_formation or rng.choice(names)
    if home_formation not in FORMATIONS:
        raise ValueError(f"Unsupported home formation: {home_formation}")
    if away_formation is None:
        away_formation = rng.choice([name for name in names if name != home_formation])
    if away_formation not in FORMATIONS:
        raise ValueError(f"Unsupported away formation: {away_formation}")
    return [
        Team("HOME", "Home Synthetic Team", "HOME", home_formation),
        Team("AWAY", "Away Synthetic Team", "AWAY", away_formation),
    ]


def create_players(teams: list[Team]) -> list[Player]:
    players = []
    for team in teams:
        for number, position in enumerate(FORMATIONS[team.formation], start=1):
            players.append(Player(f"{team.team_id}_P{number:02d}", team.team_id,
                                  f"{team.short_name} Player {number:02d}", position, number))
    return players


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def to_world_x(attacking_x: float, direction: int) -> float:
    return clamp(attacking_x if direction == 1 else 100.0 - attacking_x)


def to_attacking_x(world_x: float, direction: int) -> float:
    return clamp(world_x if direction == 1 else 100.0 - world_x)


def player_anchor(player: Player) -> tuple[float, float]:
    x, y = POSITION_ANCHORS.get(player.position, (50.0, 50.0))
    # Keep players sharing a role from occupying exactly the same synthetic point.
    if player.position in {"CB", "CM", "CDM", "ST"}:
        y += -6.0 if player.shirt_number % 2 else 6.0
    return x, clamp(y, 5.0, 95.0)


def choose_nearest_player(rng: random.Random, players: list[Player], attacking_x: float,
                          y: float, excluded_player_id: Optional[str] = None) -> Player:
    candidates = [p for p in players if p.player_id != excluded_player_id] or players
    return min(candidates, key=lambda p: (
        (player_anchor(p)[0] - attacking_x) ** 2 + (player_anchor(p)[1] - y) ** 2
        + rng.uniform(0.0, 90.0)
    ))


def choose_action(rng: random.Random, attacking_x: float, scenario: str,
                  focal_team_has_ball: bool, counterattack_left: int) -> str:
    if scenario == "harmless_possession":
        weights = {"pass": 0.76, "carry": 0.20, "cross": 0.025, "shot": 0.015}
    elif attacking_x >= 72:
        weights = {"pass": 0.37, "carry": 0.16, "cross": 0.22, "shot": 0.25}
    elif attacking_x >= 52:
        weights = {"pass": 0.55, "carry": 0.25, "cross": 0.12, "shot": 0.08}
    else:
        weights = {"pass": 0.66, "carry": 0.27, "cross": 0.05, "shot": 0.02}

    if scenario == "counterattack" and focal_team_has_ball and counterattack_left > 0:
        weights = {"pass": 0.48, "carry": 0.40, "cross": 0.06, "shot": 0.06}
        if attacking_x >= 68:
            weights = {"pass": 0.30, "carry": 0.25, "cross": 0.15, "shot": 0.30}
    elif scenario == "defensive_dominance" and not focal_team_has_ball:
        weights["shot"] *= 0.45
        weights["cross"] *= 0.65
        weights["pass"] += 0.08

    actions = list(weights)
    return rng.choices(actions, weights=[weights[a] for a in actions], k=1)[0]


def make_event(*, event_id: str, match_id: str, timestamp: int, team_id: str,
               player_id: str, event_type: str, x: float, y: float, possession_id: str,
               possession_team_id: str, period: int, x_end: Optional[float] = None,
               y_end: Optional[float] = None, success: Optional[bool] = None,
               pressure: float = 0.0, speed: float = 0.0,
               receiver_player_id: Optional[str] = None) -> Event:
    distance = 0.0 if x_end is None or y_end is None else ((x_end - x) ** 2 + (y_end - y) ** 2) ** 0.5
    return Event(
        event_id=event_id, match_id=match_id, timestamp_seconds=timestamp, team_id=team_id,
        player_id=player_id, event_type=event_type, x=round(clamp(x), 2), y=round(clamp(y), 2),
        x_end=None if x_end is None else round(clamp(x_end), 2),
        y_end=None if y_end is None else round(clamp(y_end), 2),
        pressure=round(clamp(pressure, 0.0, 1.0), 3), speed=round(max(0.0, speed), 2),
        distance=round(distance, 2), success=success, possession_id=possession_id,
        possession_team_id=possession_team_id, period=period, receiver_player_id=receiver_player_id,
    )


def generate_match(seed: int = 42, home_formation: Optional[str] = None,
                   away_formation: Optional[str] = None, scenario: str = "balanced",
                   scenario_team_id: str = "HOME",
                   duration_seconds: int = DEFAULT_DURATION_SECONDS) -> dict:
    """Generate a match dictionary that can be saved as JSON.

    Supported scenarios: balanced, high_pressing, counterattack,
    defensive_dominance, harmless_possession. Scenarios change probabilities and
    event patterns; a later analytics engine must determine whether a shift occurred.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario!r}. Choose from {sorted(SCENARIOS)}")
    if scenario_team_id not in {"HOME", "AWAY"}:
        raise ValueError("scenario_team_id must be 'HOME' or 'AWAY'")
    if not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    if duration_seconds < 60:
        raise ValueError("duration_seconds must be at least 60 seconds")

    rng = random.Random(seed)
    teams = create_teams(rng, home_formation, away_formation)
    players = create_players(teams)
    players_by_team = {
        team_id: [p for p in players if p.team_id == team_id]
        for team_id in ("HOME", "AWAY")
    }
    match_id = f"MATCH_{seed:04d}"
    match = Match(
        match_id=match_id, home_team_id="HOME", away_team_id="AWAY",
        start_time="2026-01-01T15:00:00", status="completed",
        duration_seconds=duration_seconds, home_attacks_positive_x_first_half=True,
    )

    events: list[Event] = []
    current_time = 0
    event_number = 1
    possession_number = 0
    opening_team = rng.choice(["HOME", "AWAY"])
    current_team_id = opening_team
    last_world_point = (50.0, 50.0)
    second_half_started = False
    next_start_is_kickoff = True
    counterattack_actions_left = 0
    pressure_rate = {
        "balanced": 0.16,
        "high_pressing": 0.48,
        "counterattack": 0.20,
        "defensive_dominance": 0.40,
        "harmless_possession": 0.07,
    }[scenario]

    while current_time < duration_seconds:
        # Switch ends and restart at midfield at half-time.
        if not second_half_started and current_time >= HALF_TIME_SECONDS:
            second_half_started = True
            current_time = HALF_TIME_SECONDS + 1
            current_team_id = other_team(opening_team)
            last_world_point = (50.0, 50.0)
            next_start_is_kickoff = True
            counterattack_actions_left = 0
        if current_time >= duration_seconds:
            break

        period = 2 if second_half_started else 1
        possession_number += 1
        possession_id = f"POS_{possession_number:04d}"
        possession_team_id = current_team_id
        team_players = players_by_team[current_team_id]
        direction = match.attacking_direction(current_team_id, period)

        if next_start_is_kickoff:
            world_x, ball_y = 50.0, 50.0
            attacking_x = to_attacking_x(world_x, direction)
            actor = choose_nearest_player(rng, team_players, attacking_x, ball_y)
            receiver = choose_nearest_player(
                rng, team_players, attacking_x + 5.0, ball_y, actor.player_id
            )
            end_x = to_world_x(clamp(attacking_x + 4.0), direction)
            events.append(make_event(
                event_id=f"EV_{event_number:06d}", match_id=match_id,
                timestamp=current_time, team_id=current_team_id, player_id=actor.player_id,
                event_type="pass", x=world_x, y=ball_y, x_end=end_x, y_end=ball_y,
                possession_id=possession_id, possession_team_id=possession_team_id,
                period=period, success=True, speed=rng.uniform(8.0, 17.0),
                receiver_player_id=receiver.player_id,
            ))
            event_number += 1
            last_world_point = (end_x, ball_y)
            current_time += rng.randint(3, 6)
            next_player_id: Optional[str] = receiver.player_id
            next_start_is_kickoff = False
        else:
            world_x, ball_y = last_world_point
            attacking_x = to_attacking_x(world_x, direction)
            actor = choose_nearest_player(rng, team_players, attacking_x, ball_y)
            events.append(make_event(
                event_id=f"EV_{event_number:06d}", match_id=match_id,
                timestamp=current_time, team_id=current_team_id, player_id=actor.player_id,
                event_type="recovery", x=world_x, y=ball_y,
                possession_id=possession_id, possession_team_id=possession_team_id,
                period=period, success=True, pressure=rng.uniform(0.2, 0.75),
                speed=rng.uniform(2.0, 6.0),
            ))
            event_number += 1
            next_player_id = actor.player_id
            current_time += rng.randint(2, 5)

        possession_ended = False
        action_limit = rng.randint(3, 7)
        actions_completed = 0

        while actions_completed < action_limit and current_time < duration_seconds:
            next_time = current_time + rng.randint(2, 7)
            if period == 1 and next_time >= HALF_TIME_SECONDS:
                current_time = HALF_TIME_SECONDS
                break
            if next_time >= duration_seconds:
                current_time = duration_seconds
                break
            current_time = next_time

            direction = match.attacking_direction(current_team_id, period)
            world_x, ball_y = last_world_point
            attacking_x = to_attacking_x(world_x, direction)
            defender_team_id = other_team(current_team_id)
            defender_direction = match.attacking_direction(defender_team_id, period)
            focal_team_has_ball = current_team_id == scenario_team_id

            local_pressure_rate = pressure_rate
            if scenario == "high_pressing":
                local_pressure_rate = 0.62 if defender_team_id == scenario_team_id else 0.24
            elif scenario == "defensive_dominance":
                local_pressure_rate = 0.56 if defender_team_id == scenario_team_id else 0.18

            # A defensive action belongs to the possession it challenges. If it
            # wins the ball, the next possession gets a new ID and the defender
            # becomes possession_team_id for that next sequence.
            if rng.random() < local_pressure_rate:
                defender_players = players_by_team[defender_team_id]
                defender_x = to_attacking_x(world_x, defender_direction)
                defender = choose_nearest_player(rng, defender_players, defender_x, ball_y)
                defensive_type = rng.choices(
                    ["pressure", "tackle", "interception"], [0.65, 0.22, 0.13], k=1
                )[0]
                win_probability = 0.20
                if scenario == "high_pressing":
                    win_probability = 0.34 if defender_team_id == scenario_team_id else 0.18
                elif scenario == "defensive_dominance":
                    win_probability = 0.32 if defender_team_id == scenario_team_id else 0.13
                won_ball = rng.random() < win_probability
                events.append(make_event(
                    event_id=f"EV_{event_number:06d}", match_id=match_id,
                    timestamp=current_time, team_id=defender_team_id,
                    player_id=defender.player_id, event_type=defensive_type,
                    x=world_x, y=ball_y, possession_id=possession_id,
                    possession_team_id=possession_team_id, period=period,
                    success=won_ball, pressure=rng.uniform(0.45, 1.0),
                    speed=rng.uniform(2.0, 7.0),
                ))
                event_number += 1
                if won_ball:
                    current_team_id = defender_team_id
                    counterattack_actions_left = 3
                    possession_ended = True
                    break
                current_time += rng.randint(1, 3)
                if period == 1 and current_time >= HALF_TIME_SECONDS:
                    current_time = HALF_TIME_SECONDS
                    break
                if current_time >= duration_seconds:
                    break

            # Choose a ball action based on pitch zone and scenario.
            world_x, ball_y = last_world_point
            attacking_x = to_attacking_x(world_x, direction)
            action = choose_action(
                rng, attacking_x, scenario, focal_team_has_ball, counterattack_actions_left
            )
            actor = next((p for p in team_players if p.player_id == next_player_id), None)
            if actor is None:
                actor = choose_nearest_player(rng, team_players, attacking_x, ball_y)
            next_player_id = None

            if action == "pass":
                success_probability = 0.84
                if scenario == "high_pressing":
                    success_probability = 0.73
                elif scenario == "harmless_possession":
                    success_probability = 0.92
                success = rng.random() < success_probability
                if scenario == "harmless_possession":
                    progress = rng.uniform(-3.0, 3.5)
                elif scenario == "counterattack" and focal_team_has_ball and counterattack_actions_left > 0:
                    progress = rng.uniform(9.0, 20.0)
                else:
                    progress = rng.uniform(-5.0, 13.0)
                if not success:
                    progress = rng.uniform(-5.0, 10.0)
                end_attacking_x = clamp(attacking_x + progress)
                end_y = clamp(ball_y + rng.uniform(-14.0, 14.0), 4.0, 96.0)
                end_x = to_world_x(end_attacking_x, direction)
                receiver = choose_nearest_player(
                    rng, team_players, end_attacking_x, end_y, actor.player_id
                )
                events.append(make_event(
                    event_id=f"EV_{event_number:06d}", match_id=match_id,
                    timestamp=current_time, team_id=current_team_id,
                    player_id=actor.player_id, event_type="pass", x=world_x, y=ball_y,
                    x_end=end_x, y_end=end_y, possession_id=possession_id,
                    possession_team_id=possession_team_id, period=period,
                    success=success, pressure=rng.uniform(0.05, 0.85),
                    speed=rng.uniform(8.0, 22.0), receiver_player_id=receiver.player_id,
                ))
                event_number += 1
                last_world_point = (end_x, end_y)
                if success:
                    next_player_id = receiver.player_id
                else:
                    current_team_id = defender_team_id
                    counterattack_actions_left = 3
                    possession_ended = True

            elif action == "carry":
                success = rng.random() < (0.76 if scenario != "harmless_possession" else 0.94)
                if scenario == "harmless_possession":
                    progress = rng.uniform(-1.0, 3.0)
                elif scenario == "counterattack" and focal_team_has_ball and counterattack_actions_left > 0:
                    progress = rng.uniform(8.0, 19.0)
                else:
                    progress = rng.uniform(3.0, 11.0)
                if not success:
                    progress = rng.uniform(0.0, 8.0)
                end_attacking_x = clamp(attacking_x + progress)
                end_y = clamp(ball_y + rng.uniform(-8.0, 8.0), 4.0, 96.0)
                end_x = to_world_x(end_attacking_x, direction)
                events.append(make_event(
                    event_id=f"EV_{event_number:06d}", match_id=match_id,
                    timestamp=current_time, team_id=current_team_id,
                    player_id=actor.player_id, event_type="carry", x=world_x, y=ball_y,
                    x_end=end_x, y_end=end_y, possession_id=possession_id,
                    possession_team_id=possession_team_id, period=period,
                    success=success, pressure=rng.uniform(0.1, 0.9),
                    speed=rng.uniform(2.5, 7.5),
                ))
                event_number += 1
                last_world_point = (end_x, end_y)
                if not success:
                    current_team_id = defender_team_id
                    counterattack_actions_left = 3
                    possession_ended = True

            elif action == "cross":
                success = rng.random() < (0.34 if scenario != "harmless_possession" else 0.10)
                end_attacking_x = clamp(max(attacking_x + rng.uniform(3.0, 12.0), 78.0))
                end_y = rng.uniform(38.0, 62.0)
                end_x = to_world_x(end_attacking_x, direction)
                receiver = choose_nearest_player(
                    rng, team_players, end_attacking_x, end_y, actor.player_id
                )
                events.append(make_event(
                    event_id=f"EV_{event_number:06d}", match_id=match_id,
                    timestamp=current_time, team_id=current_team_id,
                    player_id=actor.player_id, event_type="cross", x=world_x, y=ball_y,
                    x_end=end_x, y_end=end_y, possession_id=possession_id,
                    possession_team_id=possession_team_id, period=period,
                    success=success, pressure=rng.uniform(0.1, 0.95),
                    speed=rng.uniform(10.0, 24.0), receiver_player_id=receiver.player_id,
                ))
                event_number += 1
                last_world_point = (end_x, end_y)
                if success:
                    next_player_id = receiver.player_id
                else:
                    current_team_id = defender_team_id
                    counterattack_actions_left = 3
                    possession_ended = True

            else:  # shot
                target_y = clamp(50.0 + rng.uniform(-12.0, 12.0), 5.0, 95.0)
                goal_line_x = to_world_x(100.0, direction)
                on_target = rng.random() < (0.08 if scenario == "harmless_possession" else 0.34)
                events.append(make_event(
                    event_id=f"EV_{event_number:06d}", match_id=match_id,
                    timestamp=current_time, team_id=current_team_id,
                    player_id=actor.player_id, event_type="shot", x=world_x, y=ball_y,
                    x_end=goal_line_x, y_end=target_y, possession_id=possession_id,
                    possession_team_id=possession_team_id, period=period,
                    success=on_target, pressure=rng.uniform(0.05, 0.9),
                    speed=rng.uniform(18.0, 32.0),
                ))
                event_number += 1
                last_world_point = (goal_line_x, target_y)
                current_team_id = defender_team_id
                counterattack_actions_left = 3
                possession_ended = True

            actions_completed += 1
            if counterattack_actions_left > 0:
                counterattack_actions_left -= 1
            if possession_ended:
                break

        if current_time >= duration_seconds:
            break
        # If we reached half-time, start the second half on the next outer iteration.
        if not second_half_started and current_time >= HALF_TIME_SECONDS:
            continue

        if not possession_ended and actions_completed >= action_limit and current_time < duration_seconds:
            # Put an explicit failed action at the end of a possession that reached its cap.
            current_time += 1
            if period == 1 and current_time >= HALF_TIME_SECONDS:
                current_time = HALF_TIME_SECONDS
                continue
            world_x, ball_y = last_world_point
            direction = match.attacking_direction(current_team_id, period)
            attacking_x = to_attacking_x(world_x, direction)
            actor = choose_nearest_player(rng, players_by_team[current_team_id], attacking_x, ball_y)
            events.append(make_event(
                event_id=f"EV_{event_number:06d}", match_id=match_id,
                timestamp=current_time, team_id=current_team_id,
                player_id=actor.player_id, event_type="turnover", x=world_x, y=ball_y,
                possession_id=possession_id, possession_team_id=possession_team_id,
                period=period, success=False, pressure=rng.uniform(0.2, 0.9),
                speed=rng.uniform(2.0, 6.0),
            ))
            event_number += 1
            current_team_id = other_team(current_team_id)
            counterattack_actions_left = 3

        current_time += rng.randint(2, 5)

    return {
        "match": asdict(match),
        "teams": [asdict(team) for team in teams],
        "players": [asdict(player) for player in players],
        "events": [asdict(event) for event in events],
        "metadata": {
            "seed": seed,
            "scenario": scenario,
            "scenario_team_id": scenario_team_id,
            "duration_seconds": duration_seconds,
            "synthetic_data": True,
            "coordinate_system": "shared pitch frame; x and y each range from 0 to 100",
            "x_direction": "opposite attacking directions; teams switch ends at half-time",
            "possession_id_semantics": "events share an ID for one possession sequence; possession changes start a new ID",
            "possession_team_id_semantics": "team controlling the ball immediately before the event outcome",
            "distance_unit": "normalized pitch-coordinate units, not metres",
            "momentum_shift_forced_by_scenario": False,
        },
    }


def save_match(match_data: dict, filepath: str | Path) -> Path:
    """Write a generated match to JSON and return its path."""
    output_path = Path(filepath)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(match_data, file, indent=2, ensure_ascii=False)
        file.write("\n")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic Shift11 football match.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="balanced")
    parser.add_argument("--scenario-team", choices=["HOME", "AWAY"], default="HOME")
    parser.add_argument("--home-formation", choices=sorted(FORMATIONS))
    parser.add_argument("--away-formation", choices=sorted(FORMATIONS))
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION_SECONDS)
    parser.add_argument("--output", default="data/match_001.json")
    args = parser.parse_args()
    data = generate_match(seed=args.seed, scenario=args.scenario,
                          scenario_team_id=args.scenario_team,
                          home_formation=args.home_formation,
                          away_formation=args.away_formation,
                          duration_seconds=args.duration)
    path = save_match(data, args.output)
    print(f"Generated match: {path}")
    print(f"Teams: {len(data['teams'])}")
    print(f"Players: {len(data['players'])}")
    print(f"Events: {len(data['events'])}")
    print(f"Scenario: {data['metadata']['scenario']}")
    print(f"Seed: {data['metadata']['seed']}")


if __name__ == "__main__":
    main()
