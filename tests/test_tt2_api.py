"""Exercise the real connector boundary without sending tokens to GameHive."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from streamlit.proto.TextInput_pb2 import TextInput

from src import tt2_api as api
from src.tt2_player import parse_player


APP_TOKEN = "11111111-1111-4111-8111-111111111111"
PLAYER_TOKEN = "22222222-2222-4222-8222-222222222222"
ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = {
    "name": "API test player", "total_skill_points": "500", "max_stage": 50000,
    "skill_tree": [], "artifacts": [
        {"artifact_id": "Artifact20", "level": "10", "is_enchanted": True}],
    "seasonal_artifacts": [], "equipment_set": [],
    "relics_received": "1e50", "relics_spent": "2e49",
    "seasonal_relics_received": "100", "seasonal_relics_spent": "25",
}


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        api._next_attempt.clear()
        self.session_patch = patch.object(api.requests, "Session")
        self.session = self.session_patch.start().return_value.__enter__.return_value
        self.addCleanup(self.session_patch.stop)
        self.socket_patch = patch("socketio.Client")
        self.socket = self.socket_patch.start().return_value
        self.addCleanup(self.socket_patch.stop)
        handlers = {}
        self.socket.on.side_effect = lambda name, handler, **kwargs: handlers.update({name: handler})
        self.socket.connect.side_effect = lambda *args, **kwargs: handlers["connected"]()
        self.response = self.session.post.return_value.__enter__.return_value
        self.response.status_code = 200
        self.response.iter_content.return_value = [json.dumps(PAYLOAD).encode()]

    def test_socket_auth_stays_open_until_rest_finishes(self):
        def post(*args, **kwargs):
            self.socket.disconnect.assert_not_called()
            return self.session.post.return_value
        self.session.post.side_effect = post
        data = api.fetch_player(APP_TOKEN, PLAYER_TOKEN)
        self.socket.connect.assert_called_once_with(
            api.BASE_URL, headers={"API-Authenticate": APP_TOKEN},
            transports=["websocket"], namespaces=["/player"],
            socketio_path="api", wait_timeout=12, retry=False,
        )
        call = self.session.post.call_args
        self.assertEqual(call.args[0], api.BASE_URL + "/player/data")
        self.assertEqual(call.kwargs["json"]["player_token"], PLAYER_TOKEN)
        self.assertNotIn("verify", call.kwargs)  # Requests' default TLS verification.
        self.assertFalse(call.kwargs["allow_redirects"])
        player = parse_player(data, "GameHive API")
        self.assertEqual(player.total_sp, 500)
        self.assertTrue(player.skills_known)
        self.assertEqual(player.mementos, 75)
        self.assertEqual(player.relics, 8 * 10**49)
        self.assertIn("Artifact20", player.enchanted)
        self.socket.disconnect.assert_called_once()

    def test_repeat_request_is_blocked_without_network(self):
        api.fetch_player(APP_TOKEN, PLAYER_TOKEN)
        with self.assertRaisesRegex(api.APIError, "Wait"):
            api.fetch_player(APP_TOKEN, PLAYER_TOKEN)
        self.socket.connect.assert_called_once()
        self.session.post.assert_called_once()
        self.assertNotIn(APP_TOKEN, repr(api._next_attempt))
        self.assertNotIn(PLAYER_TOKEN, repr(api._next_attempt))

    def test_bad_uuid_does_not_connect(self):
        with self.assertRaisesRegex(api.APIError, "application"):
            api.fetch_player("bad", PLAYER_TOKEN)
        self.socket.connect.assert_not_called()

    def test_socket_failure_is_redacted_and_cleaned_up(self):
        self.socket.connect.side_effect = RuntimeError(APP_TOKEN + PLAYER_TOKEN)
        with self.assertRaises(api.APIError) as caught:
            api.fetch_player(APP_TOKEN, PLAYER_TOKEN)
        self.assertNotIn(APP_TOKEN, str(caught.exception))
        self.assertNotIn(PLAYER_TOKEN, str(caught.exception))
        self.session.post.assert_not_called()
        self.socket.disconnect.assert_called_once()

    def test_http_rejection_rate_limit_and_bad_payload(self):
        for status, body, message in (
            (403, {}, "denied"), (429, {}, "limit"), (503, {}, "HTTP 503"),
            (200, {"message": PLAYER_TOKEN}, "did not return"),
        ):
            with self.subTest(status=status):
                api._next_attempt.clear()
                self.response.status_code = status
                self.response.headers = {"Retry-After": "300"}
                self.response.iter_content.return_value = [json.dumps(body).encode()]
                with self.assertRaisesRegex(api.APIError, message) as caught:
                    api.fetch_player(APP_TOKEN, PLAYER_TOKEN)
                self.assertNotIn(PLAYER_TOKEN, str(caught.exception))
                if status == 429:
                    self.assertGreater(next(iter(api._next_attempt.values())) - api.time.monotonic(), 290)

    def test_unreadable_and_oversized_responses_are_rejected(self):
        for chunks in ([b"not json"], [b"x" * 5_000_001]):
            api._next_attempt.clear()
            self.response.iter_content.return_value = chunks
            with self.assertRaises(api.APIError):
                api.fetch_player(APP_TOKEN, PLAYER_TOKEN)


class APIUITests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict("os.environ", {"TT2_APPLICATION_TOKEN": APP_TOKEN})
        self.env.start()
        self.addCleanup(self.env.stop)

    def app(self):
        return AppTest.from_file(str(ROOT / "player_optimizer.py"), default_timeout=30).run()

    def test_import_forget_and_clear(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_input(key="tt2_api_player").proto.type, TextInput.PASSWORD)
        app.text_input(key="tt2_api_player").input(PLAYER_TOKEN)
        with patch("src.tt2_ui.fetch_player", return_value=PAYLOAD) as fetch:
            next(b for b in app.button if b.label == "Import from TT2").click().run()
        self.assertFalse(app.exception)
        fetch.assert_called_once_with(APP_TOKEN, PLAYER_TOKEN)
        self.assertEqual(app.metric[0].value, "500")
        self.assertTrue(any("Player imported" in s.value for s in app.success))
        next(b for b in app.button if b.label == "Forget player token").click().run()
        self.assertEqual(app.text_input(key="tt2_api_player").value, "")
        self.assertEqual(app.metric[0].value, "500")
        next(b for b in app.button if b.label == "Clear imported player").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.metric)

    def test_error_retains_previous_import_and_plan(self):
        app = self.app()
        app.text_area(key="json_input").input((ROOT / "examples/player-demo.json").read_text()).run()
        next(b for b in app.button if b.label == "Import player").click().run()
        with patch("src.tt2_ui.fetch_player", side_effect=api.APIError("Check both tokens.")):
            next(b for b in app.button if b.label == "Import from TT2").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "1,500")
        self.assertTrue(any("Check both tokens" in e.value for e in app.error))

    def test_server_application_token_is_not_exposed(self):
        with patch.dict("os.environ", {"TT2_APPLICATION_TOKEN": APP_TOKEN}):
            app = AppTest.from_file(str(ROOT / "player_optimizer.py"), default_timeout=30).run()
            self.assertFalse(any(t.key == "tt2_api_application" for t in app.text_input))
            app.text_input(key="tt2_api_player").input(PLAYER_TOKEN)
            with patch("src.tt2_ui.fetch_player", return_value=PAYLOAD) as fetch:
                next(b for b in app.button if b.label == "Import from TT2").click().run()
            self.assertFalse(app.exception)
            fetch.assert_called_once_with(APP_TOKEN, PLAYER_TOKEN)
            self.assertFalse(any(APP_TOKEN in m.value for m in app.markdown))

    def test_json_only_deployment_needs_no_tokens(self):
        with patch.dict("os.environ", {"TT2_APPLICATION_TOKEN": ""}), patch("streamlit.secrets", {}):
            app = self.app()
        self.assertFalse(app.exception)
        self.assertFalse(app.text_input)
        self.assertTrue(app.text_area(key="json_input"))


if __name__ == "__main__":
    unittest.main()
