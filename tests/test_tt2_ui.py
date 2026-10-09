import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class PlayerUITests(unittest.TestCase):
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
