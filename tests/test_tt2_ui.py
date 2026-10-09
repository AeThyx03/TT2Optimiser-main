import unittest
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
        self.assertIn("Primary effect does not benefit this build", rosabella)
        self.assertIn("companions", rosabella)

    def test_collection_priorities_and_filters(self):
        app = self.app()
        app.text_area(key="json_input").input((ROOT / "examples/player-demo.json").read_text()).run()
        self.click(app, "Import player")
        self.assertFalse(app.exception)
        self.assertTrue(any("Focus upgrades on" in x.value for x in app.info))
        cards = [x.value for x in app.markdown if "collection-card" in x.value]
        self.assertTrue(any("Upgrade first" in x for x in cards))
        self.assertTrue(any("data:image/png;base64" in x for x in cards))
        app.text_input(key="search_monuments").input("no matching monument").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("No items match" in x.value for x in app.info))

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
        app.toggle[0].set_value(True).run()
        self.assertTrue(any("inputs changed" in x.value for x in app.info))
        self.click(app, "Optimize skill points")
        self.assertFalse(app.exception)
        self.assertTrue(any("QoL utility gain" in x.value for x in app.caption))
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
