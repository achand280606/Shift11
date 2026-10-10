"""Behavioural checks for causal continuity in Shift11 match events."""

import unittest

from src.generator import generate_match


class EventContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = generate_match(seed=42, scenario="balanced")
        cls.events = cls.data["events"]

    def test_event_ids_are_unique(self):
        event_ids = [event["event_id"] for event in self.events]
        self.assertEqual(len(event_ids), len(set(event_ids)))

    def test_successful_pass_has_a_valid_receiver(self):
        players = {
            player["player_id"]: player
            for player in self.data["players"]
        }

        for event in self.events:
            if event["event_type"] == "pass" and event["success"]:
                receiver_id = event["receiver_player_id"]
                self.assertIsNotNone(receiver_id, event["event_id"])
                self.assertIn(receiver_id, players)
                self.assertEqual(
                    players[receiver_id]["team_id"],
                    event["team_id"],
                )

    def test_event_possession_owner_matches_its_team_for_on_ball_actions(self):
        on_ball_actions = {
            "pass", "carry", "cross", "shot", "recovery"
        }

        for event in self.events:
            if event["event_type"] in on_ball_actions:
                self.assertEqual(
                    event["team_id"],
                    event["possession_team_id"],
                    f"Unexpected possession ownership at {event['event_id']}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)