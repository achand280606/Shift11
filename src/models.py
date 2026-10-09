
from dataclasses import dataclass
from typing import Optional


# Shared pitch coordinates:
# x = 0 to 100 along the length of the pitch
# y = 0 to 100 across the width of the pitch
PITCH_MIN = 0.0
PITCH_MAX = 100.0

# Regulation match: two 45-minute halves.
FIRST_HALF_END_SECONDS = 45 * 60
MATCH_DURATION_SECONDS = 90 * 60


@dataclass
class Team:
    team_id: str
    name: str
    short_name: str
    formation: str


@dataclass
class Player:
    player_id: str
    team_id: str
    name: str
    position: str
    shirt_number: int


@dataclass
class Match:
    match_id: str
    home_team_id: str
    away_team_id: str
    start_time: str
    status: str

    duration_seconds: int = MATCH_DURATION_SECONDS

    # By default, the home team attacks toward increasing x in the first half.
    # The away team attacks in the opposite direction.
    home_attacks_positive_x_first_half: bool = True

    def attacking_direction(self, team_id: str, period: int) -> int:
        """
        Return 1 when a team attacks toward increasing x, or -1
        when it attacks toward decreasing x.

        Period 1 = first half
        Period 2 = second half
        """

        if team_id not in (self.home_team_id, self.away_team_id):
            raise ValueError(f"Unknown team_id: {team_id}")

        if period not in (1, 2):
            raise ValueError("period must be 1 (first half) or 2 (second half)")

        home_attacks_positive_x = self.home_attacks_positive_x_first_half

        # Teams switch attacking directions at half-time.
        if period == 2:
            home_attacks_positive_x = not home_attacks_positive_x

        if team_id == self.home_team_id:
            return 1 if home_attacks_positive_x else -1

        return -1 if home_attacks_positive_x else 1


@dataclass
class Event:
    event_id: str
    match_id: str
    timestamp_seconds: int
    team_id: str
    player_id: Optional[str]
    event_type: str

    # Start location in shared pitch coordinates, each from 0 to 100.
    x: float
    y: float

    # End location for actions that move the ball, such as passes and carries.
    x_end: Optional[float] = None
    y_end: Optional[float] = None

    pressure: float = 0.0
    speed: float = 0.0
    distance: float = 0.0

    success: Optional[bool] = None

    # Events in the same possession should share the same possession_id.
    # These remain optional temporarily for compatibility with existing data.
    possession_id: Optional[str] = None
    possession_team_id: Optional[str] = None

    # Period 1 = first half; period 2 = second half.
    period: int = 1

    # Useful for passes. Can be empty for events with no receiver.
    receiver_player_id: Optional[str] = None
