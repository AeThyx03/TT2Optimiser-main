"""On-demand GameHive imports. Credentials are never written to disk or cached.

Protocol: https://tt2-docs.gamehivegames.com/rest/openapi.yaml and /socket/.
The /player socket must remain authenticated while POST /player/data runs.
"""
from contextlib import suppress
import hashlib
import json
import math
from threading import Event, Lock
import time
from uuid import UUID

import requests


BASE_URL = "https://tt2-public.gamehivegames.com"
PLAYER_PROPERTIES = (
    "name", "max_stage", "total_skill_points", "skill_tree", "artifacts",
    "seasonal_artifacts", "equipment_set", "relics_received", "relics_spent",
    "seasonal_relics_received", "seasonal_relics_spent",
)
COOLDOWN = 120
_lock = Lock()
_next_attempt = {}  # Only credential hashes and monotonic deadlines; no player data.


class APIError(ValueError):
    """A safe user-facing error; never include upstream bodies or exceptions."""


def _token(value, label):
    try:
        return str(UUID(value.strip()))
    except (ValueError, AttributeError, TypeError):
        raise APIError(f"Enter a valid {label} token (UUID).") from None


def fetch_player(application_token, player_token):
    """Fetch once, with verified TLS, bounded waits, no redirects or auto-retry.

    The process-wide gate also covers failed attempts and separate UI sessions.
    GameHive enforces the same limit across deployments and process restarts.
    """
    application_token = _token(application_token, "application")
    player_token = _token(player_token, "player")
    try:
        import socketio
    except ImportError:
        raise APIError("Install the updated requirements.txt and restart the optimiser to enable TT2 imports.") from None

    fingerprint = hashlib.sha256(f"{application_token}:{player_token}".encode()).hexdigest()
    now = time.monotonic()
    with _lock:
        remaining = _next_attempt.get(fingerprint, 0) - now
        if remaining > 0:
            raise APIError(f"Wait {math.ceil(remaining)} seconds before importing this player again.")
        for key in list(_next_attempt):
            if _next_attempt[key] <= now:
                del _next_attempt[key]
        _next_attempt[fingerprint] = now + COOLDOWN

    ready, failed = Event(), Event()
    with requests.Session() as session:
        sio = socketio.Client(
            reconnection=False, request_timeout=12, http_session=session,
            logger=False, engineio_logger=False,
        )

        def connected(*args):
            ready.set()

        def rejected(*args):
            failed.set()
            ready.set()

        sio.on("connected", connected, namespace="/player")
        sio.on("error", rejected, namespace="/player")
        sio.on("connect_error", rejected, namespace="/player")
        try:
            sio.connect(
                BASE_URL, headers={"API-Authenticate": application_token},
                transports=["websocket"], namespaces=["/player"],
                socketio_path="api", wait_timeout=12, retry=False,
            )
            if not ready.wait(12) or failed.is_set():
                raise APIError("GameHive did not authorize the player connection. Check your application token and try again after two minutes.")
            with session.post(
                BASE_URL + "/player/data",
                headers={"API-Authenticate": application_token},
                json={"player_token": player_token, "properties": list(PLAYER_PROPERTIES)},
                timeout=(12, 20), allow_redirects=False, stream=True,
            ) as response:
                if response.status_code == 429:
                    # Honor a longer server cooldown if supplied, without a retry loop.
                    try:
                        delay = max(COOLDOWN, float(response.headers.get("Retry-After", COOLDOWN)))
                        if not math.isfinite(delay):
                            delay = COOLDOWN
                    except (ValueError, TypeError):
                        delay = COOLDOWN
                    with _lock:
                        _next_attempt[fingerprint] = time.monotonic() + delay
                    raise APIError("GameHive's request limit was reached. Wait at least two minutes (or the server's longer cooldown) before trying again.")
                if response.status_code in (401, 403):
                    raise APIError("GameHive denied access. Check both tokens and confirm the player token has not been revoked.")
                if response.status_code != 200:
                    raise APIError(f"GameHive returned HTTP {response.status_code}. Wait two minutes before trying again.")
                body = bytearray()
                for chunk in response.iter_content(65536):
                    body.extend(chunk)
                    if len(body) > 5_000_000:
                        raise APIError("GameHive's response exceeded the 5 MB import limit.")
                try:
                    payload = json.loads(body)
                except (ValueError, UnicodeError, RecursionError):
                    raise APIError("GameHive returned an unreadable response. Your existing player has been kept.") from None
                if not isinstance(payload, dict) or "total_skill_points" not in payload:
                    raise APIError("GameHive did not return the requested player data. Check your tokens; your existing player has been kept.")
                return payload
        except APIError:
            raise
        except requests.exceptions.SSLError:
            raise APIError("The secure connection to GameHive could not be verified. Check the hosting computer's certificate trust and network; certificate checks remain enabled.") from None
        except Exception:
            # Socket/HTTP exceptions may contain credentials or upstream response bodies.
            raise APIError("Could not connect to GameHive. Check the network and application token, then try again after two minutes. No automatic retries were made.") from None
        finally:
            with suppress(Exception):
                sio.disconnect()
