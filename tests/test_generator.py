"""Basic automated checks for the Shift11 synthetic match generator."""
import unittest

from src.generator import SCENARIOS, generate_match
from src.models import Match


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = generate_match(seed=42, scenario="balanced")

    def test_reproducible_with_same_seed(self):
        self.assertEqual(self.data, generate_match(seed=42, scenario="balanced"))

    def test_two_teams_and_twenty_two_players(self):
        self.assertEqual(len(self.data["teams"]), 2)
        self.assertEqual(len(self.data["players"]), 22)
        self.assertEqual(sum(p["team_id"] == "HOME" for p in self.data["players"]), 11)
        self.assertEqual(sum(p["team_id"] == "AWAY" for p in self.data["players"]), 11)

    def test_event_coordinates_are_in_bounds(self):
        for event in self.data["events"]:
            self.assertTrue(0 <= event["x"] <= 100)
            self.assertTrue(0 <= event["y"] <= 100)
            if event["x_end"] is not None:
                self.assertTrue(0 <= event["x_end"] <= 100)
            if event["y_end"] is not None:
                self.assertTrue(0 <= event["y_end"] <= 100)

    def test_event_times_are_ordered_and_periods_match(self):
        events = self.data["events"]
        self.assertTrue(all(
            events[i]["timestamp_seconds"] <= events[i + 1]["timestamp_seconds"]
            for i in range(len(events) - 1)
        ))
        for event in events:
            if event["period"] == 1:
                self.assertLess(event["timestamp_seconds"], 45 * 60)
            else:
                self.assertEqual(event["period"], 2)
                self.assertGreater(event["timestamp_seconds"], 45 * 60)

    def test_players_belong_to_the_team_performing_each_event(self):
        player_teams = {p["player_id"]: p["team_id"] for p in self.data["players"]}
        for event in self.data["events"]:
            self.assertIn(event["player_id"], player_teams)
            self.assertEqual(player_teams[event["player_id"]], event["team_id"])
            receiver_id = event["receiver_player_id"]
            if receiver_id is not None:
                self.assertIn(receiver_id, player_teams)
                self.assertEqual(player_teams[receiver_id], event["team_id"])

    def test_each_possession_id_has_one_declared_possession_owner(self):
        owners_by_possession = {}
        for event in self.data["events"]:
            possession_id = event["possession_id"]
            self.assertIsNotNone(possession_id)
            owner = event["possession_team_id"]
            if possession_id in owners_by_possession:
                self.assertEqual(owners_by_possession[possession_id], owner)
            else:
                owners_by_possession[possession_id] = owner

    def test_directions_switch_at_half_time(self):
        match = Match("M1", "HOME", "AWAY", "2026-01-01T15:00:00", "scheduled")
        self.assertEqual(match.attacking_direction("HOME", 1), 1)
        self.assertEqual(match.attacking_direction("AWAY", 1), -1)
        self.assertEqual(match.attacking_direction("HOME", 2), -1)
        self.assertEqual(match.attacking_direction("AWAY", 2), 1)

    def test_scenarios_are_supported_without_forcing_shift_results(self):
        for scenario in SCENARIOS:
            result = generate_match(seed=9, scenario=scenario, duration_seconds=900)
            self.assertEqual(result["metadata"]["scenario"], scenario)
            self.assertFalse(result["metadata"]["momentum_shift_forced_by_scenario"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
