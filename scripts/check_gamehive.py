"""One manual, read-only connectivity check; never prints credentials or payloads."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.tt2_api import APIError, fetch_player
from src.tt2_player import ImportError, parse_player


def main():
    path = ROOT / ".tt2-local.json"
    local = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    application = os.getenv("TT2_APPLICATION_TOKEN", local.get("application_token", ""))
    player_token = os.getenv("TT2_PLAYER_TOKEN", local.get("player_token", ""))
    try:
        player = parse_player(fetch_player(application, player_token))
    except (APIError, ImportError) as e:
        print(str(e))
        return 2
    print(f"API verified: {player.total_sp:,} SP, {len(player.artifacts)} artifacts, {len(player.monuments)} monuments.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
