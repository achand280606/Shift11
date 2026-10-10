"""Initial tests for Shift11 deterministic match-state analytics."""

import unittest

from src.analytics import (
    calculate_window_metrics,
    generate_metric_series,
)
from src.generator import generate_match


class AnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = generate_match(
            seed=42,
            scenario="balanced",
            duration_seconds=900,
        )

    def test_metrics_return_both_teams(self):
        result = calculate_window_metrics(self.data, end_time=600)
        self.assertEqual(set(result), {"HOME", "AWAY"})

    def test_empty_window_returns_zero_counts(self):
        result = calculate_window_metrics(
            self.data,
            end_time=1,
            window_seconds=1,
        )
        for team_metrics in result.values():
            self.assertEqual(team_metrics["event_count"], 0.0)
            self.assertEqual(team_metrics["shots"], 0.0)
            self.assertEqual(team_metrics["crosses"], 0.0)

    def test_metric_counts_are_non_negative(self):
        result = calculate_window_metrics(self.data, end_time=600)
        count_keys = (
            "event_count",
            "pressure_actions",
            "successful_defensive_actions",
            "shots",
            "crosses",
            "final_third_entries",
            "possession_events",
        )
        for team_metrics in result.values():
            for key in count_keys:
                self.assertGreaterEqual(team_metrics[key], 0.0)

    def test_defensive_success_rate_is_bounded(self):
        result = calculate_window_metrics(self.data, end_time=600)
        for team_metrics in result.values():
            self.assertGreaterEqual(team_metrics["defensive_success_rate"], 0.0)
            self.assertLessEqual(team_metrics["defensive_success_rate"], 1.0)

    def test_series_uses_requested_interval(self):
        series = generate_metric_series(
            self.data,
            window_seconds=300,
            interval_seconds=30,
        )
        self.assertTrue(series)
        self.assertEqual(series[0]["timestamp_seconds"], 30)
        self.assertEqual(series[1]["timestamp_seconds"], 60)

    def test_invalid_window_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_window_metrics(self.data, end_time=600, window_seconds=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)