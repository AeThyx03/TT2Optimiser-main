"""Server-only GameHive access. No token logging, redirects, or automatic retries."""
import time
from uuid import UUID

import requests

API_URL = "https://tt2-public.gamehivegames.com/player/data"
PROPERTIES = ["name", "max_stage", "total_skill_points", "skill_tree", "artifacts", "seasonal_artifacts", "equipment_set", "relics_received", "relics_spent", "seasonal_relics_received", "seasonal_relics_spent", "total_pet_levels", "crafting_shards_spent"]


class APIError(ValueError):
    pass


def fetch_player(application_token, player_token, state=None, request=requests.post):
    for value in (application_token, player_token):
        try:
            UUID(value.strip())
        except (ValueError, AttributeError):
            raise APIError("Both tokens must be valid UUIDs.") from None
    if state is not None:
        now = time.monotonic()
        if now - state.get("last_api_attempt", -1e10) < 30:
            raise APIError("Wait 30 seconds between API requests.")
        state["last_api_attempt"] = now
    try:
        response = request(API_URL, headers={"API-Authenticate": application_token.strip()},
                           json={"player_token": player_token.strip(), "properties": PROPERTIES},
                           timeout=(5, 20), allow_redirects=False)
    except requests.exceptions.SSLError:
        raise APIError("The network could not verify GameHive's TLS certificate. Use JSON import or a network that permits GameHive; certificate checks stay enabled.") from None
    except requests.RequestException:
        raise APIError("Could not reach GameHive. Check your connection or use JSON import.") from None
    if response.status_code != 200:
        messages = {401: "Application token rejected.", 403: "Access refused. Check token permissions or the network filter.",
                    429: "GameHive rate limit reached. Try again later."}
        raise APIError(messages.get(response.status_code, f"GameHive returned HTTP {response.status_code}. No automatic retry was made."))
    try:
        result = response.json()
    except ValueError:
        raise APIError("GameHive returned a non-JSON response. Use JSON import.") from None
    if not isinstance(result, dict) or "_error" in result or "error" in result:
        raise APIError("GameHive rejected the player-data request. Verify token access before trying again.")
    return result
