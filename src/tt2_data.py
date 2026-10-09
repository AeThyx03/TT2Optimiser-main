"""Pinned, offline game data. No network requests during calculation."""
import csv
import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "tt2"
BUILDS = ("Clan Ship", "Shadow Clone", "Heavenly Strike", "Pet", "Dagger", "Gold Gun")
GOLD_SOURCES = ("Fairy", "Heart of Gold", "Chesterson")


def table(name):
    with (DATA / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def catalog():
    sources = json.loads((DATA / "sources.json").read_text(encoding="utf-8-sig"))
    skills = {r["TalentID"]: r for r in table("SkillTreeInfo2.0.csv")}
    for s in skills.values():
        s["max"] = int(s["MaxLevel"])
        s["costs"] = [0]
        for level in range(s["max"]):
            s["costs"].append(s["costs"][-1] + int(s[f"Co{level}"]))
    return {
        "skills": skills,
        "artifacts": {r["ArtifactID"]: r for r in table("ArtifactInfo.csv")},
        "monuments": {r["ArtifactID"]: r for r in table("EndgameSeasonArtifactInfo.csv")},
        "reductions": json.loads((DATA / "reductions.json").read_text()),
        "spells": json.loads((DATA / "spells.json").read_text()),
        "spell_reductions": json.loads((DATA / "spell_reductions.json").read_text()),
        # Upstream UpdateInfo.csv can lag the current game data release.
        "version": sources.get("game_version", table("UpdateInfo.csv")[0]["Version"]),
        "sources": sources,
    }
