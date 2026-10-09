
from dataclasses import dataclass
from typing import Optional


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


@dataclass
class Event:
    event_id: str
    match_id: str
    timestamp_seconds: int
    team_id: str
    player_id: Optional[str]
    event_type: str

    x: float
    y: float
    x_end: Optional[float] = None
    y_end: Optional[float] = None

    pressure: float = 0.0
    speed: float = 0.0
    distance: float = 0.0

    success: Optional[bool] = None
    possession_id: Optional[str] = None
