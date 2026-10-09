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
    # This alternate season, rather than the latest table, matches the supplied
    # player's 33 owned IDs, caps, effects and displayed multiplier magnitudes.
    monuments = {r["ArtifactID"]: r for r in table("EndgameSeasonArtifactInfo_1.csv")}
    # ID 33 is not in the export; its upstream name conflicts with verified ID 6.
    # Keep its identity unresolved instead of guessing another display name.
    monuments["SeasonalArtifact33"]["Name"] = "Unverified monument (SeasonalArtifact33)"
    monuments["SeasonalArtifact33"]["PrimaryModelAvailable"] = False
    references = json.loads((DATA / "monument_descriptions.json").read_text())["monuments"]
    for key, reference in references.items():
        item = monuments[key]
        item["LegacyName"] = item["Name"]
        # A description establishes effect routing, not coefficients for a
        # changed effect. Never apply the old effect's growth to a new one.
        item["PrimaryModelAvailable"] = item["BonusType"] == reference["BonusType"]
        item.update({k: reference[k] for k in ("Name", "BonusType", "CategoryID", "Description")})
        item["MaxLevel"] = str(reference["MaxLevel"])
        item["DescriptionSource"] = reference["Image"]
        item["IsActive"] = "TRUE"  # supplied season; only owned items are ranked
    return {
        "skills": skills,
        "artifacts": {r["ArtifactID"]: r for r in table("ArtifactInfo.csv")},
        "monuments": monuments,
        "monument_source": "EndgameSeasonArtifactInfo_1.csv, cross-checked with supplied screenshots and export",
        "bonuses": {r["BonusType"]: r for r in table("BonusInfo.csv")},
        "reductions": json.loads((DATA / "reductions.json").read_text()),
        "spells": json.loads((DATA / "spells.json").read_text()),
        "spell_reductions": json.loads((DATA / "spell_reductions.json").read_text()),
        # Upstream UpdateInfo.csv can lag the current game data release.
        "version": sources.get("game_version", table("UpdateInfo.csv")[0]["Version"]),
        "sources": sources,
    }
