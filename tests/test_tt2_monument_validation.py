import json
import math
import unittest

from src.tt2_monument_validation import validate_purchases, supplied_screenshot_check


class MonumentValidationTests(unittest.TestCase):
    def test_supplied_screenshots_reject_cost_curve_despite_rounding(self):
        report = supplied_screenshot_check()
        self.assertTrue(report["contradicted_even_with_rounding"])
        self.assertAlmostEqual(report["observed_investment_ratio"], 1.9175, places=4)
        self.assertLess(report["modeled_investment_ratio"], 1.04)
        for row in report["shared_damage_checks"]:
            self.assertAlmostEqual(row["Observed next-level damage gain log10"], row["Predicted next-level damage gain log10"], delta=.001)

    def test_live_targets_display_estimates_without_validation_gate(self):
        from pathlib import Path
        from src.tt2_player import parse_player
        from src.tt2_optimizer import monument_lifetime_targets, Settings
        p = parse_player((Path(__file__).parent / "fixtures/monument-player.json").read_text())
        targets = monument_lifetime_targets(p, Settings(build="Heavenly Strike"))
        self.assertGreater(targets["SeasonalArtifact43"], 0)
        self.assertGreater(targets["SeasonalArtifact51"], 0)
        self.assertEqual(targets["SeasonalArtifact6"], 0)

    def observations(self):
        rows = []
        for key in ("SeasonalArtifact43", "SeasonalArtifact51"):
            for level in (1000, 2000):
                rows.append({"monument": key, "level_before": level, "level_after": level + 10,
                             "mementos_spent": 1e20 * 8 * math.fsum(l ** 2.26 for l in range(level, level + 10))})
        return rows

    def test_relative_cost_agreement_and_detects_bad_curve(self):
        rows = self.observations()
        report = validate_purchases(json.dumps(rows))
        self.assertTrue(report["costs_match"])
        rows[-1]["mementos_spent"] *= 2
        report = validate_purchases(json.dumps(rows))
        self.assertFalse(report["costs_match"])
        self.assertIn("fails", report["verdict"])

    def test_single_purchase_cannot_validate_curve(self):
        report = validate_purchases(json.dumps(self.observations()[:1]))
        self.assertFalse(report["sufficient"])
        self.assertFalse(report["costs_match"])

    def test_measured_damage_mismatch(self):
        rows = self.observations()
        rows[0].update(damage_before_percent="1e500", damage_after_percent="1e600")
        report = validate_purchases(json.dumps(rows))
        self.assertIn("Mismatch", report["rows"][0]["Shared damage check"])

    def test_invalid_and_duplicate_observations(self):
        for payload in ('{}', '[{}]', '[{"monument":"SeasonalArtifact43","level_before":2,"level_after":1,"mementos_spent":10}]'):
            with self.assertRaises(ValueError):
                validate_purchases(payload)
        rows = self.observations()[:1] * 2
        with self.assertRaises(ValueError):
            validate_purchases(json.dumps(rows))
