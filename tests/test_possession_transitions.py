"""Tests for possession transitions in Shift11 generated matches."""

import unittest

from src.generator import generate_match


class PossessionTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = generate_match(seed=42, scenario="balanced")
        cls.events = cls.data["events"]

    def test_possession_ids_do_not_reappear_after_another_possession(self):
        closed_ids = set()
        previous_id = None

        for event in self.events:
            current_id = event["possession_id"]

            if current_id != previous_id:
                if previous_id is not None:
                    closed_ids.add(previous_id)

                self.assertNotIn(
                    current_id,
                    closed_ids,
                    f"Possession {current_id} reappeared after ending",
                )

            previous_id = current_id

    def test_terminal_events_are_followed_by_a_new_possession(self):
        terminal_events = {
            "shot",
            "turnover",
        }

        for index, event in enumerate(self.events[:-1]):
            next_event = self.events[index + 1]

            ends_possession = (
                event["event_type"] in terminal_events
                or (
                    event["event_type"] in {"pass", "carry", "cross"}
                    and event["success"] is False
                )
                or (
                    event["event_type"] in {"tackle", "interception"}
                    and event["success"] is True
                )
            )

            if ends_possession:
                self.assertNotEqual(
                    event["possession_id"],
                    next_event["possession_id"],
                    f"{event['event_type']} at {event['event_id']} "
                    "was not followed by a new possession",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)