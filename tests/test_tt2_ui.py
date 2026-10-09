import unittest
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class PlayerUITests(unittest.TestCase):
    def test_rosabella_heavenly_strike_card(self):
        app = self.app()
        app.text_area(key="json_input").input('{"total_skill_points":500,"monuments":{"Rosabella\'s Village":93000,"SeasonalArtifact43":93000}}').run()
        self.click(app, "Import player")
        next(s for s in app.selectbox if s.label == "Damage type").select("Heavenly Strike").run()
        self.assertFalse(app.exception)
        cards = [x.value for x in app.markdown if "collection-card" in x.value]
        rosabella = next(x for x in cards if "Rosabella" in x)
        self.assertNotIn("Upgrade first", rosabella)
        self.assertIn("Not recommended", rosabella)
        self.assertIn("0.00% target of lifetime mementos", rosabella)
        self.assertNotIn("companions", rosabella)

    def test_collection_priorities(self):
        app = self.app()
        payload = json.loads((ROOT / "tests/fixtures/monument-player.json").read_text())
        payload["artifacts"] = {"Artifact20": 10}
        app.text_area(key="json_input").input(json.dumps(payload)).run()
        self.click(app, "Import player")
        self.assertFalse(app.exception)
        next(s for s in app.selectbox if s.label == "Damage type").select("Heavenly Strike").run()
        cards = [x.value for x in app.markdown if "collection-card" in x.value]
        self.assertTrue(any("Upgrade first" in x for x in cards))
        self.assertTrue(any("data:image/png;base64" in x for x in cards))
        rosabella = next(x for x in cards if "Rosabella" in x)
        self.assertIn("Not recommended", rosabella)
        self.assertNotIn("Upgrade first", rosabella)
        self.assertIn("0.00% target of lifetime mementos", rosabella)
        self.assertFalse(any("% of best relative value" in x for x in cards))
        glassbone = next(x for x in cards if "The Glassbone Menagerie" in x)
        self.assertIn("target of lifetime mementos", glassbone)
        self.assertNotIn("Current lifetime share", glassbone)
        self.assertEqual(sum('The Glassbone Menagerie</h4>' in x for x in cards), 1)
        self.assertFalse(any(x.key == "affordable_monuments" for x in app.checkbox))
        self.assertFalse(any(x.key in ("search_monuments", "search_artifacts") for x in app.text_input))
        self.assertFalse(any(x.label in ("Show ranked upgrades only", "Show affordable upgrades only") for x in app.checkbox))

    def app(self):
        return AppTest.from_file(str(ROOT / "player_optimizer.py"), default_timeout=30).run()

    @staticmethod
    def click(app, label):
        next(b for b in app.button if b.label == label).click().run()

    def test_paste_optimize_change_build_and_clear(self):
        app = self.app()
        self.assertFalse(app.exception)
        app.text_area(key="json_input").input((ROOT / "examples/player-demo.json").read_text()).run()
        self.click(app, "Import player")
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "1,500")
        self.assertEqual(app.metric[1].value, "4")
        self.assertEqual(app.metric[2].value, "1,496")
        self.click(app, "Optimize skill points")
        self.assertFalse(app.exception)
        self.assertTrue(any("Valid plan" in x.value for x in app.success))
        self.assertFalse(any(r.label == "Allocation view" for r in app.radio))
        app.radio(key="optimization_goal").set_value("Speed").run()
        self.assertTrue(any("inputs changed" in x.value for x in app.info))
        self.click(app, "Optimize skill points")
        self.assertFalse(app.exception)
        self.assertTrue(any("Speed utility gain" in x.value for x in app.caption))
        self.assertEqual(app.radio(key="optimization_goal").value, "Speed")
        app.radio(key="optimization_goal").set_value("Balanced").run()
        self.assertTrue(any("inputs changed" in x.value for x in app.info))
        self.click(app, "Optimize skill points")
        self.assertTrue(any("Balanced · Damage/gold gain" in x.value for x in app.caption))
        next(s for s in app.selectbox if s.label == "Damage type").select("Pet").run()
        self.assertTrue(any("inputs changed" in x.value for x in app.info))
        self.click(app, "Optimize skill points")
        self.assertFalse(app.exception)
        self.click(app, "Clear imported player")
        self.assertFalse(app.exception)
        self.assertFalse(app.metric)

    def test_invalid_then_valid_paste(self):
        app = self.app()
        app.text_area(key="json_input").input("not JSON").run()
        self.click(app, "Import player")
        self.assertTrue(app.error)
        self.assertFalse(app.exception)
        app.text_area(key="json_input").input((ROOT / "examples/player-demo.json").read_text()).run()
        self.click(app, "Import player")
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "1,500")
        next(r for r in app.radio if r.label == "Planning mode").set_value("Spend available points").run()
        self.click(app, "Optimize skill points")
        self.assertFalse(app.exception)
        self.assertTrue(any("Valid plan" in x.value for x in app.success))


if __name__ == "__main__":
    unittest.main()
