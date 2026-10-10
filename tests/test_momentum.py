
"""Tests for Shift11's deterministic momentum score engine."""

import unittest

from src.generator import generate_match
from src.momentum import (
    calculate_momentum_scores,
    generate_momentum_series,
)


class MomentumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = generate_match(
            seed=42,
            scenario="balanced",
            duration_seconds=900,
        )

    def test_both_teams_receive_scores(self):
        result = calculate_momentum_scores(self.data, end_time=600)
        self.assertEqual(
            set(result["scores"]),
            {"HOME", "AWAY"},
        )

    def test_scores_are_bounded(self):
        result = calculate_momentum_scores(self.data, end_time=600)
        for score in result["scores"].values():
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 100.0)

    def test_team_scores_sum_to_100(self):
        result = calculate_momentum_scores(self.data, end_time=600)
        self.assertAlmostEqual(
            sum(result["scores"].values()),
            100.0,
            places=2,
        )

    def test_component_shares_sum_to_100(self):
        result = calculate_momentum_scores(self.data, end_time=600)

        for component in result["components"]["HOME"]:
            total = (
                result["components"]["HOME"][component]
                + result["components"]["AWAY"][component]
            )
            self.assertAlmostEqual(total, 100.0, places=2)

    
    def test_empty_window_is_balanced(self):
        result = calculate_momentum_scores(
            self.data,
            end_time=-1,
            window_seconds=300,
        )
        self.assertEqual(result["scores"]["HOME"], 50.0)
        self.assertEqual(result["scores"]["AWAY"], 50.0)

    def test_series_uses_requested_interval(self):
        series = generate_momentum_series(
            self.data,
            window_seconds=300,
            interval_seconds=30,
        )
        self.assertEqual(series[0]["timestamp_seconds"], 30)
        self.assertEqual(series[1]["timestamp_seconds"], 60)

    def test_invalid_window_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_momentum_scores(
                self.data,
                end_time=600,
                window_seconds=0,
            )

    def test_invalid_interval_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_momentum_series(
                self.data,
                interval_seconds=0,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
