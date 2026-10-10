"""Tests for the Shift11 synthetic match data validator."""

from copy import deepcopy
import unittest

from src.generator import generate_match
from src.validation import validate_match_data


class ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.valid_data = generate_match(seed=42, scenario="balanced")

    def test_generated_match_passes_validation(self):
        errors = validate_match_data(self.valid_data)
        self.assertEqual(errors, [], "\n".join(errors))

    def test_rejects_coordinates_outside_pitch(self):
        data = deepcopy(self.valid_data)
        data["events"][0]["x"] = -1

        errors = validate_match_data(data)
        self.assertTrue(
            any("start coordinates are outside 0..100" in error for error in errors),
            "Expected an out-of-bounds coordinate error.",
        )

    def test_rejects_unknown_possession_owner(self):
        data = deepcopy(self.valid_data)
        data["events"][0]["possession_team_id"] = "UNKNOWN_TEAM"

        errors = validate_match_data(data)
        self.assertTrue(
            any("unknown possession_team_id" in error for error in errors),
            "Expected an unknown possession owner error.",
        )

    def test_rejects_broken_spatial_continuity(self):
        data = deepcopy(self.valid_data)
        events = data["events"]
        pair_found = False

        for first, second in zip(events, events[1:]):
            same_possession = first.get("possession_id") == second.get("possession_id")
            has_endpoint = first.get("x_end") is not None and first.get("y_end") is not None
            if same_possession and first.get("possession_id") and has_endpoint:
                # Move the second event far away while keeping coordinates valid.
                second["x"] = 100 if float(first["x_end"]) < 50 else 0
                pair_found = True
                break

        self.assertTrue(pair_found, "No adjacent same-possession pair with an endpoint was found.")

        errors = validate_match_data(data)
        self.assertTrue(
            any("starts" in error and "coordinate units" in error for error in errors),
            "Expected a spatial continuity error.",
        )

    def test_rejects_successful_pass_without_receiver(self):
        data = deepcopy(self.valid_data)
        successful_pass = next(
            (
                event for event in data["events"]
                if event.get("event_type") == "pass" and event.get("success") is True
            ),
            None,
        )
        self.assertIsNotNone(successful_pass, "Generated match did not contain a successful pass.")
        successful_pass["receiver_player_id"] = None

        errors = validate_match_data(data)
        self.assertTrue(
            any("missing receiver_player_id" in error for error in errors),
            "Expected an error for a successful pass without a receiver.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
