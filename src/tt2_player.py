"""Validate and normalize in-game exports and the GameHive player API."""
import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from src.tt2_data import catalog


class ImportError(ValueError):
    pass


def number(value, label, integer=False):
    try:
        if isinstance(value, bool):
            raise ValueError
        n = Decimal(str(value).replace(",", "").strip())
        if not n.is_finite() or n < 0 or n.adjusted() > 10000:
            raise ValueError
        if integer and n != n.to_integral_value():
            raise ValueError
        return n
    except (InvalidOperation, ValueError, TypeError):
        raise ImportError(f"{label} must be a finite, non-negative {'integer' if integer else 'number'}.") from None


def first(obj, *keys, default=None):
    return next((obj[k] for k in keys if k in obj and obj[k] is not None), default)


def levels(value, id_key, label):
    if value is None:
        return {}, set()
    if isinstance(value, list):
        pairs = []
        for row in value:
            if not isinstance(row, dict) or id_key not in row:
                raise ImportError(f"Each {label} entry needs {id_key} and level.")
            pairs.append((row[id_key], row))
    elif isinstance(value, dict):
        pairs = list(value.items())
    else:
        raise ImportError(f"{label} must be an object or an array.")
    result, enchanted = {}, set()
    for key, row in pairs:
        if not isinstance(key, str) or key in result:
            raise ImportError(f"{label} contains an invalid or duplicate ID.")
        # Game exports use compact "lv" fields for inventory entries, while the
        # GameHive API and normalized examples use "level"/"Level".
        val = first(row, "level", "Level", "lv", "Lv") if isinstance(row, dict) else row
        result[key] = number(val, f"{label} {key} level", integer=True)
        if isinstance(row, dict) and first(row, "is_enchanted", "enchanted", "e", default=False) in (True, 1, "true"):
            enchanted.add(key)
    return result, enchanted


@dataclass
class Player:
    name: str
    total_sp: int
    max_stage: int
    skills: dict
    artifacts: dict
    monuments: dict
    equipment: set
    enchanted: set
    relics: Decimal | None
    mementos: Decimal | None
    version: str = ""
    warnings: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    skills_known: bool = True
    source: str = "JSON"
    monument_enchanted: set = field(default_factory=set)

    @property
    def spent_sp(self):
        return sum(catalog()["skills"][key]["costs"][level] for key, level in self.skills.items())

    @property
    def available_sp(self):
        return self.total_sp - self.spent_sp


def parse_player(payload, source="JSON"):
    if isinstance(payload, str):
        if len(payload) > 5_000_000:
            raise ImportError("Export exceeds the 5 MB limit.")
        def unique(pairs):
            out = {}
            for k, v in pairs:
                if k in out:
                    raise ImportError(f"Duplicate JSON key: {k}")
                out[k] = v
            return out
        try:
            payload = json.loads(payload, object_pairs_hook=unique, parse_int=Decimal, parse_float=Decimal)
        except (json.JSONDecodeError, RecursionError):
            raise ImportError("Invalid JSON. Paste the complete in-game export, including its braces.") from None
    if not isinstance(payload, dict):
        raise ImportError("Expected a player JSON object.")
    for wrapper in ("data", "player", "player_data"):
        if wrapper in payload and isinstance(payload[wrapper], dict):
            payload = payload[wrapper]
    stats = payload.get("playerStats", payload)
    if not isinstance(stats, dict):
        raise ImportError("playerStats must be an object.")
    total = first(stats, "Skill Points Owned", "total_skill_points", "totalSkillPoints", "skill_points")
    if total is None:
        raise ImportError("Missing total skill points. Use a full player export with playerStats → Skill Points Owned, or API total_skill_points.")
    total = number(total, "Total skill points", True)
    if total > 200_000:
        raise ImportError("Total skill points exceeds the supported limit of 200,000.")
    stage = number(first(stats, "Max Prestige Stage", "max_stage", default=0), "Max stage", True)
    if stage > 1_000_000_000:
        raise ImportError("Max stage exceeds the supported limit of 1,000,000,000.")
    data = catalog()
    warnings = []
    raw_skills = first(payload, "skillTree", "skill_tree", "skills")
    skills, _ = levels(raw_skills, "skill_id", "Skills")
    aliases = {s["Name"]: key for key, s in data["skills"].items()}
    skills = {aliases.get(k, k): v for k, v in skills.items()}
    unknown = [k for k, v in skills.items() if k not in data["skills"] and v]
    if unknown:
        raise ImportError("Unknown allocated skills: " + ", ".join(unknown) + ". Update the data tables before calculating SP.")
    skills = {k: int(v) for k, v in skills.items() if k in data["skills"] and v}
    for k, v in skills.items():
        if v > data["skills"][k]["max"]:
            raise ImportError(f"{data['skills'][k]['Name']} exceeds this snapshot's level cap. Update the game tables.")
    artifacts, enchanted = levels(first(payload, "artifacts", "Artifacts"), "artifact_id", "Artifacts")
    monuments, monument_enchanted = levels(first(payload, "seasonal_artifacts", "seasonalArtifacts", "monuments"), "artifact_id", "Monuments")
    for collection, kind in ((artifacts, "artifacts"), (monuments, "monuments")):
        name_map = {s["Name"]: k for k, s in data[kind].items()}
        for k, item in data[kind].items():
            if "LegacyName" in item:
                name_map.setdefault(item["LegacyName"], k)
        for k in list(collection):
            if k in name_map:
                target = name_map[k]
                collection[target] = collection.pop(k)
                enchanted_ids = enchanted if kind == "artifacts" else monument_enchanted
                if k in enchanted_ids:
                    enchanted_ids.remove(k)
                    enchanted_ids.add(target)
        missing = [k for k in collection if k not in data[kind]]
        if missing:
            warnings.append(f"Unknown {kind} retained without recommendations: {', '.join(missing)}.")
    sets = first(payload, "equipmentSets", "equipment_set", default=[])
    if not isinstance(sets, list) or not all(isinstance(x, str) for x in sets):
        raise ImportError("Equipment sets must be an array of IDs.")

    def balance(direct, received, spent, stat_name):
        raw = first(payload, *direct, default=stats.get(stat_name))
        if raw is not None:
            return number(raw, stat_name)
        if received in payload and spent in payload:
            # Match precision to the operands so huge scientific values do not lose a small balance.
            from decimal import localcontext
            a, b = number(payload[received], received), number(payload[spent], spent)
            with localcontext() as ctx:
                ctx.prec = max(50, a.adjusted() + 2, b.adjusted() + 2)
                delta = a - b
            if delta < 0:
                raise ImportError(f"{stat_name}: spent exceeds received.")
            return delta
        return None

    player = Player(
        name=str(first(stats, "Player Name", "name", default=payload.get("name", "Imported player")))[:120],
        total_sp=int(total), max_stage=int(stage),
        skills=skills, artifacts=artifacts, monuments=monuments, equipment=set(sets), enchanted=enchanted,
        relics=balance(("relics", "available_relics"), "relics_received", "relics_spent", "Relics"),
        mementos=balance(("mementos", "available_mementos"), "seasonal_relics_received", "seasonal_relics_spent", "Mementos"),
        version=str(first(payload, "version", "Version", default=stats.get("Game Version", ""))),
        warnings=warnings, stats=stats, skills_known=raw_skills is not None, source=source,
        monument_enchanted=monument_enchanted,
    )
    if player.spent_sp > player.total_sp:
        raise ImportError(f"Allocated skills cost {player.spent_sp:,} SP but the export reports {player.total_sp:,} total. Check the export and data version.")
    if not player.skills_known:
        warnings.append("Skill allocation is missing. Spent and available SP are unknown; only a full respec can be planned.")
    if not player.max_stage:
        warnings.append("Max stage is missing or zero; stage-gated skills will stay locked.")
    if player.version and player.version != data["version"]:
        warnings.append(f"Export version {player.version} differs from game-data snapshot {data['version']}. Confirm compatibility before applying recommendations.")
    return player
