import math
from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest

from src.tt2_season import MonumentEffect, compare_monuments, compare_prestige_times, log_multiplier


ROOT = Path(__file__).resolve().parents[1]


class SeasonComparisonTests(unittest.TestCase):
    def test_changed_monument_values_can_reverse_build_order(self):
        shared = MonumentEffect("shared", ("Dagger", "Pet"), "Damage", log_multiplier("x1e8000"))
        dagger = MonumentEffect("monument-a", ("Dagger",), "Damage", log_multiplier("x1e600"))
        self.assertEqual(compare_monuments([shared, dagger], 0.7)[0][0], "Dagger")
        pet = MonumentEffect("monument-b", ("Pet",), "Gold", log_multiplier("x1e900"))
        self.assertEqual(compare_monuments([shared, dagger, pet], 0.7)[0][0], "Pet")
        self.assertEqual(compare_monuments([shared, dagger, pet], 0)[0][0], "Dagger")

    def test_reads_display_notation_without_exponent_overflow(self):
        self.assertEqual(log_multiplier("x1e8500"), 8500)
        self.assertAlmostEqual(log_multiplier("+50%"), math.log10(1.5))
        self.assertAlmostEqual(log_multiplier("+1e8500%"), 8498)
        for value in ("NaN", "Infinity", "0.5", "50%", "x1e99999", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                log_multiplier(value)

    def test_run_comparison_uses_median_instead_of_best_attempt(self):
        self.assertEqual(
            compare_prestige_times({"Pet": [45, 50, 55], "Dagger": [35, 65, 70], "Clan Ship": []}),
            [("Pet", 50, 3), ("Dagger", 65, 3)],
        )

    def test_ui_records_boosts_and_compares_only_matching_stage_ranges(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run()

        def click(label):
            next(button for button in app.button if button.label == label).click().run()
            self.assertFalse(app.exception)

        def field(widgets, label):
            return next(widget for widget in widgets if widget.label == label)

        # An unknown ID is still usable without any bundled monument table.
        app.text_area(key="json_input").input('{"total_skill_points": 100, "monuments": {"NewSeasonMonument": 50}}')
        click("Import player")
        field(app.multiselect, "Builds receiving this bonus").set_value(["Pet"])
        field(app.text_input, "Current bonus").input("x1e800")
        click("Save bonus")
        self.assertTrue(any("Best supported by recorded monuments · Pet" in element.value for element in app.success))

        for build, target, seconds in (("Pet", 200000, 30), ("Dagger", 210000, 25)):
            field(app.number_input, "Start stage").set_value(190000)
            field(app.number_input, "Target stage").set_value(target)
            field(app.selectbox, "Timed build").select(build)
            field(app.number_input, "Elapsed seconds").set_value(seconds)
            click("Save timed run")
        self.assertFalse(any("Fastest measured" in element.value for element in app.success))

        field(app.number_input, "Target stage").set_value(200000)
        click("Save timed run")
        self.assertTrue(any("Fastest measured · Dagger" in element.value for element in app.success))

        click("Import player")
        self.assertFalse(app.success)


if __name__ == "__main__":
    unittest.main()
