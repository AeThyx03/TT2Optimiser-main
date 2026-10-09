"""Deterministic, prerequisite-aware heuristic; scores are modeled log10 gains.

Skill effect cases and reduction factors are adapted from rawrzcookie's MIT
optimizer. This is not a full gameplay simulator or a proof of global optimality.
"""
import math
from dataclasses import dataclass
from decimal import Decimal

from src.tt2_data import BUILDS, GOLD_SOURCES, catalog


@dataclass(frozen=True)
class Settings:
    build: str = "Clan Ship"
    gold: str = "Fairy"
    gold_weight: float = 0.7
    contracts: bool = False
    lightning_attempts: int = 60
    qol: bool = False

    def __post_init__(self):
        if self.build not in BUILDS or self.gold not in GOLD_SOURCES:
            raise ValueError("Unsupported build or gold source.")
        if not math.isfinite(self.gold_weight) or not 0 <= self.gold_weight <= 1:
            raise ValueError("Gold weight must be between 0 and 1.")
        if not 0 <= self.lightning_attempts <= 1000:
            raise ValueError("Lightning attempts must be between 0 and 1000.")

    @property
    def gold_key(self):
        return "HoG" if self.gold == "Heart of Gold" else self.gold


def log(value):
    return math.log10(max(float(value), 1e-300))


def reduction(key, settings):
    r = catalog()["reductions"].get(key, {})
    return (r.get(settings.build) or 0) + (r.get(settings.gold_key) or 0) * settings.gold_weight


def skill_score(key, level, settings, equipment):
    if not level:
        return 0.0
    s = catalog()["skills"][key]
    def val(prefix):
        try:
            return float(s[f"{prefix}{level}"])
        except ValueError:
            return 0.0
    a, b, c = val("A"), val("B"), val("C")
    r = reduction(key, settings)
    mc = int("MultiCast" in equipment) + int("Valkyrie" in equipment)
    multicast = {"BurstDamageMultiCastSkill", "TapBoostMultiCastSkill", "DualPetMultiCast", "HelperBoostMultiCastSkill", "ClanShipVoltageMultiCastSkill", "ShadowCloneMultiCastSkill", "GuidedBlade", "StreamOfBladesMultiCastSkill", "TwilightGatheringMultiCastSkill"}
    score = r * log(a or 1)
    if key in multicast:
        score = r * (b + mc) * log(10 * a)
        if key == "TwilightGatheringMultiCastSkill":
            score += r * log(c or 1)
    elif key == "HelperBoost":
        score = r * log(1 + a)
    elif key == "HelperDmgQTE":
        score *= 5
    elif key in {"BossDmgQTE", "HelperInspiredWeaken", "ClanShipVoltage", "CriticalHit"}:
        score += r * log(b or 1)
    elif key == "PetBonusBoost":
        score += (catalog()["reductions"]["TapDmg"].get(settings.build) or 0) * log(b or 1)
    elif key in {"LoadedDice", "QuickFortune"}:
        score += settings.gold_weight * log(b or 1)
    elif key == "CloneDmg":
        score += r * log((4 + b) / 4)
    elif key == "PoisonedBlade":
        score = r * log(1 + a * 10)
    elif key == "CritSkillBoost":
        score = -r * sum(log(max(1 - a * b**i, 1e-12)) for i in range(settings.lightning_attempts))
    elif key == "TerrifyingPact":
        score = r * log(a or 1) + log(b or 1) if settings.contracts else 0
    elif key == "KratosSummon":
        score *= b
    elif key == "HandOfMidasMultiCastSkillBoost":
        stacks = min(int(b) + mc, 5)
        aa = [1, 100, 10000, 1000000, 100000000, 1000000000]
        bb = [1, 10, 100, 1000, 10000, 50000]
        score = r * (log(aa[stacks]) + stacks * log(a or 1))
        if settings.gold != "Chesterson":
            score += settings.gold_weight * log(bb[stacks])
    extra_spells = {
        "TwilightBell": ("BurstDamage", "TwilightFairy"),
        "SummonerAutoTap": ("DualPet", "TapBoost"),
        "PhantomBlades": ("CritBoost", "StreamOfBlades"),
        "AlchemistMastery": ("HandOfMidas", "GoldenMissile"),
    }
    for spell in extra_spells.get(key, ()):
        base = 34 if "DarkAngel" in equipment else 29
        info = catalog()["spells"][spell]
        red = catalog()["spell_reductions"][spell]
        power = (red.get(settings.build) or 0) + (red.get(settings.gold_key) or 0) * settings.gold_weight
        score += power * (log(info[f"A{base + int(b)}"]) - log(info[f"A{base}"]))
    mythic = {"Knight": "FairyKnight", "Pet": "FireKnight", "Warlord": "ElectricWarlord", "Sorcerer": "WaterSorcerer", "Rogue": "EarthRogue", "Alchemist": "SteampunkKnight"}
    if mythic.get(s["Class"]) in equipment:
        score += s["costs"][level] * log(1.01)
    return score


def spent(levels):
    return sum(catalog()["skills"][k]["costs"][v] for k, v in levels.items())


# Utility weights are explicit heuristic assumptions, not damage multipliers or
# measured run times. log1p gives diminishing returns to mana/duration/skip gains.
# Each tuple is (CSV effect type, relevant builds or None, effect scale).
QOL_EFFECTS = {
    "CloakedSkipChance": (None, .1),
    "CloakedSkipChanceBoostDuringHayst": (None, .1),
    "MultiMonstersMaxCount": (None, 5),  # active farming and Silent March
    "MultiMonsters": (None, .1),
    "SpecialTitanSpawnChance": (None, .1),
    "HaystMonsterSpawnChance": (None, .1),
    "ManaPoolCap": (None, 100),
    "AllManaSourceMult": (None, .5),
    "ManaTapRegenAmount": (None, 5),
    "ManaMonsterAmount": (None, 20),
    "FairySpawnChance": (None, .5),
    "FairyCooldown": (None, 30),
    "BurstDamageSkillManaMult": ({"Heavenly Strike"}, .2),
    "BurstSkillTitanSkip": ({"Heavenly Strike"}, 10),
    "BurstSkillStageSkip": ({"Heavenly Strike"}, 10),
    "PetAttackTitanSkip": ({"Pet"}, 10),
    "PetQTEStageSkip": ({"Pet"}, 10),
    "PetAttackStageSkip": ({"Pet"}, 10),
    "PetQTECooldownMult": ({"Pet"}, .1),
    "PetTapCountToAttack": ({"Pet"}, 5),
    "AutoTapCount": ({"Pet"}, 3),
    "ClanShipTitanSkip": ({"Clan Ship"}, 10),
    "ClanShipStageSkip": ({"Clan Ship"}, 10),
    "ClanQTECooldown": ({"Clan Ship"}, 15),
    "ShadowCloneTitanSkip": ({"Shadow Clone"}, 10),
    "ShadowCloneStageSkip": ({"Shadow Clone"}, 10),
    "ShadowCloneSkillDuration": ({"Shadow Clone"}, 120),
    "UltraDaggerTitanSkip": ({"Dagger"}, 10),
    "UltraDaggerStageSkip": ({"Dagger"}, 10),
    "UltraDaggerCooldown": ({"Dagger"}, 1),
    "StreamOfBladesCooldownReduction": ({"Dagger"}, .1),
    "GoldGunTitanSkip": ({"Gold Gun"}, 10),
    "GoldGunStageSkip": ({"Gold Gun"}, 10),
    "GoldenMissileStageSkip": ({"Gold Gun"}, 20),
    "MagnumOpusDuration": ({"Gold Gun"}, 10),
    "HelperBoostSkillDuration": ({"Clan Ship", "Shadow Clone", "Gold Gun"}, 120),
    "TapBoostSkillDuration": ({"Pet", "Heavenly Strike", "Shadow Clone", "Dagger", "Gold Gun"}, 120),
    "CritBoostSkillDuration": ({"Clan Ship", "Shadow Clone", "Pet", "Dagger", "Gold Gun"}, 120),
    "HandOfMidasSkillDuration": (None, 120),
    "ShadowCloneAllSkillDurationRate": (None, .3),
    "DualPetDuration": ({"Pet"}, 120),
    "ThunderVolleySkillDuration": ({"Clan Ship"}, 120),
    "StreamOfBladesDuration": ({"Dagger"}, 120),
    "TwilightFairySkillDuration": ({"Heavenly Strike", "Shadow Clone"}, 120),
}
QOL_MULTIPLIERS = {"SpecialTitanSpawnChance", "AllManaSourceMult", "MagnumOpusDuration"}
QOL_REDUCTIONS = {"BurstDamageSkillManaMult", "PetQTECooldownMult", "ShadowCloneAllSkillDurationRate"}


def qol_score(key, level, settings):
    """Positive utility only; zero when disabled or irrelevant to this build.

    Uses owned skill rank effects from the pinned CSV. Mana recovery assumes
    access to tapping/Shadow Clone and Manni spawns; no mana sustainability,
    special-titan frequency or offline duration is simulated.
    """
    if not settings.qol or not level:
        return 0.0
    skill = catalog()["skills"][key]
    score = 0.0
    for prefix in "ABC":
        effect = skill[f"BonusType{prefix}"]
        if effect not in QOL_EFFECTS:
            continue
        builds, scale = QOL_EFFECTS[effect]
        if builds is not None and settings.build not in builds:
            continue
        value = float(skill[f"{prefix}{level}"])
        if effect in QOL_REDUCTIONS:
            gain = 1 - value
        elif effect in QOL_MULTIPLIERS:
            baseline = max(1.0, float(skill[f"{prefix}0"]))
            gain = value / baseline - 1
        else:
            gain = value - float(skill[f"{prefix}0"])
        score += 4 * math.log10(1 + max(0, gain) / scale)
    return score


def lower_tier_sp(key, levels):
    skills = catalog()["skills"]
    s = skills[key]
    return sum(skills[k]["costs"][v] for k, v in levels.items()
               if skills[k]["Branch"] == s["Branch"] and int(skills[k]["TierNum"]) < int(s["TierNum"]))


def legal_next(key, levels, max_stage):
    s = catalog()["skills"][key]
    level = levels.get(key, 0)
    if level >= s["max"] or max_stage < float(s[f"S{level}"]):
        return False
    parent = s["TalentReq"]
    return (parent == "None" or levels.get(parent, 0) > 0) and lower_tier_sp(key, levels) >= int(s["SPReq"])


def validate_allocation(levels, max_stage):
    errors = []
    skills = catalog()["skills"]
    for key, level in levels.items():
        if not level:
            continue
        s = skills.get(key)
        if not s or not isinstance(level, int) or not 0 <= level <= s["max"]:
            errors.append(f"Invalid level for {key}.")
            continue
        parent = s["TalentReq"]
        if parent != "None" and not levels.get(parent, 0):
            errors.append(f"{s['Name']} requires {skills[parent]['Name']}.")
        if lower_tier_sp(key, levels) < int(s["SPReq"]):
            errors.append(f"{s['Name']} requires {s['SPReq']} SP in lower tiers of its tree.")
        if max_stage < float(s[f"S{level-1}"]):
            errors.append(f"{s['Name']} exceeds the imported stage unlock.")
    return errors


def optimize_skills(player, settings=Settings(), mode="respec", reserve=0):
    if mode not in {"respec", "spend"}:
        raise ValueError("Unknown optimization mode.")
    if not isinstance(reserve, int) or not 0 <= reserve <= player.total_sp:
        raise ValueError("Reserved SP must be within the total budget.")
    if mode == "spend" and not player.skills_known:
        raise ValueError("Import the current skill tree before spending available points.")
    levels = dict(player.skills) if mode == "spend" else {}
    if mode == "spend":
        errors = validate_allocation(levels, player.max_stage)
        if errors:
            raise ValueError("Current tree is incompatible with this snapshot: " + " ".join(errors[:3]))
    budget = player.total_sp - reserve
    if spent(levels) > budget:
        raise ValueError("Reserved SP exceeds the points currently available.")
    skills = catalog()["skills"]
    blocked = set() if settings.contracts else {"ForbiddenContract", "RoyalContract", "TerrifyingPact"}
    damage_scores = {k: [skill_score(k, i, settings, player.equipment) for i in range(s["max"] + 1)] for k, s in skills.items()}
    utility_scores = {k: [qol_score(k, i, settings) for i in range(s["max"] + 1)] for k, s in skills.items()}
    scores = {k: [d + u for d, u in zip(damage_scores[k], utility_scores[k])] for k in skills}

    def score(tree):
        return sum(scores[k][v] for k, v in tree.items())

    def unlock(key, tree):
        s = skills[key]
        if key in blocked or player.max_stage < float(s[f"S{tree.get(key, 0)}"]):
            return False
        parent = s["TalentReq"]
        if parent != "None" and not tree.get(parent):
            if not unlock(parent, tree):
                return False
            tree[parent] = 1
        while lower_tier_sp(key, tree) < int(s["SPReq"]):
            choices = []
            for k, candidate in skills.items():
                if k in blocked or candidate["Branch"] != s["Branch"] or int(candidate["TierNum"]) >= int(s["TierNum"]):
                    continue
                if legal_next(k, tree, player.max_stage):
                    v = tree.get(k, 0)
                    cost = candidate["costs"][v+1] - candidate["costs"][v]
                    choices.append(((scores[k][v+1] - scores[k][v]) / cost, -cost, k))
            if not choices:
                return False
            k = max(choices)[2]
            tree[k] = tree.get(k, 0) + 1
            if spent(tree) >= budget:
                return False
        return True

    steps = []
    initial_score = score(levels)
    initial_damage = sum(damage_scores[k][v] for k, v in levels.items())
    initial_utility = sum(utility_scores[k][v] for k, v in levels.items())
    while spent(levels) < budget:
        base_cost, base_score = spent(levels), score(levels)
        best = None
        for key, s in skills.items():
            current = levels.get(key, 0)
            if key in blocked or current >= s["max"]:
                continue
            if max(scores[key][current:]) <= scores[key][current] + 1e-12:
                continue
            candidate = levels.copy()
            if not unlock(key, candidate):
                continue
            unlock_cost, unlock_score = spent(candidate), score(candidate)
            for target in range(current + 1, s["max"] + 1):
                if player.max_stage < float(s[f"S{target-1}"]):
                    break
                cost = unlock_cost - base_cost + s["costs"][target] - s["costs"][current]
                if cost + base_cost > budget:
                    break
                gain = unlock_score - base_score + scores[key][target] - scores[key][current]
                if gain <= 1e-12:
                    continue
                rate = gain / cost
                if best is None or rate > best[0]:
                    plan = candidate.copy()
                    plan[key] = target
                    best = (rate, plan, key, target, cost, gain)
        if best is None:
            break
        _, target_tree, key, target, cost, gain = best
        changes = "; ".join(f"{skills[k]['Name']} {levels.get(k, 0)} → {v}" for k, v in target_tree.items() if v != levels.get(k, 0))
        steps.append({"Target": skills[key]["Name"], "Level": target, "SP": cost, "Changes (includes unlocks)": changes, "Objective gain": round(gain, 4)})
        levels = target_tree
    errors = validate_allocation(levels, player.max_stage)
    if errors or spent(levels) > budget:
        raise ValueError("Unable to produce a valid allocation: " + " ".join(errors))
    return {"levels": levels, "spent": spent(levels), "remaining": player.total_sp - spent(levels),
            "steps": steps, "log_gain": sum(damage_scores[k][v] for k, v in levels.items()) - initial_damage,
            "utility_gain": sum(utility_scores[k][v] for k, v in levels.items()) - initial_utility,
            "objective_gain": score(levels) - initial_score,
            "export": {"Version": catalog()["version"], "Skills": levels}}


def bonus_weight(bonus, settings):
    """Explicit effect routing. None denotes an effect outside this model."""
    build, gold, gw = settings.build, settings.gold, settings.gold_weight
    tap = {"Clan Ship": 0, "Shadow Clone": .6, "Heavenly Strike": 1, "Pet": 1, "Dagger": 1, "Gold Gun": .45}[build]
    hero = {"Clan Ship": 1, "Shadow Clone": .6, "Heavenly Strike": .5, "Pet": .5, "Dagger": .5, "Gold Gun": .9}[build]
    if bonus in {"TapDamage", "ActiveTapDamage", "TapBoostSkillAmount"}:
        return tap
    if bonus in {"AllHelperDamage", "MeleeHelperDamage", "RangedHelperDamage", "SpellHelperDamage", "GroundHelperDamage", "FlyingHelperDamage", "HelperBoostSkillAmount", "InspiredHelperDamage", "HelperWeaponBoost", "HelperWeaponSetBoost", "ClanScrollBoost", "ClanScrollSetBoost", "HelperBoostSkillAmountDuringTapBoostSkill"}:
        return hero
    targets = {
        "BoostedSwordAttackDamage": ("Heavenly Strike", "Dagger", "Gold Gun"),
        "BuildBoostCSHSSC": ("Clan Ship", "Heavenly Strike", "Shadow Clone"),
        "BuildBoostSCPetGG": ("Shadow Clone", "Pet", "Gold Gun"),
        "PetDamage": ("Pet",), "PetAttackQTEDamage": ("Pet",), "DualPetAmount": ("Pet",),
        "ClanShipDamage": ("Clan Ship",), "CannonDamage": ("Clan Ship",), "CannonDamagePerSeasonTitan": ("Clan Ship",),
        "UltraDaggerDamage": ("Dagger",), "StreamOfBladesSkillAmount": ("Dagger",), "GoldGunDamage": ("Gold Gun",),
        "ShadowCloneSkillAmount": ("Shadow Clone",), "BurstDamageSkillAmount": ("Heavenly Strike",),
        "TwilightBoost": ("Shadow Clone", "Heavenly Strike"), "TwilightBoostPerSeasonFairy": ("Shadow Clone", "Heavenly Strike"),
        "CompanionDamage": ("Pet", "Clan Ship", "Shadow Clone"), "BuildBoostHSDGGG": ("Heavenly Strike", "Dagger", "Gold Gun"),
        "DeadlyDamageCompanion": ("Pet", "Clan Ship", "Shadow Clone"),
        "BuildBoostDGPetCS": ("Dagger", "Pet", "Clan Ship"), "SwordAttackDamage": ("Heavenly Strike", "Dagger", "Gold Gun"),
    }
    if bonus in targets:
        return float(build in targets[bonus])
    if bonus in {"FairyGold", "PetGoldQTEAmount", "GoldBoss", "ChestAmount", "MultiMonstersGold"}:
        return gw * {"FairyGold": float(gold == "Fairy"), "PetGoldQTEAmount": float(gold == "Heart of Gold"),
                     "GoldBoss": float(gold == "Heart of Gold"), "ChestAmount": float(gold in {"Fairy", "Chesterson"}),
                     "MultiMonstersGold": float(gold == "Chesterson")}[bonus]
    if bonus in {"GoldAll", "GoldSpecialty", "UnskilledGold", "JackpotGold", "GoldPerOwnedCardLevel", "GoldPerRunningActiveSkill", "GoldPerMythicSet", "JackpotGoldPerSeasonDay", "LegacyPetGoldEffect", "ExoticPetGoldEffect", "AllArtifactGoldEffect", "ArmorBoost"}:
        return gw
    if bonus == "HandOfMidasSkillAmount":
        return gw * (1 if gold == "Chesterson" else .6)
    if bonus in {"AllDamage", "BossDamage", "TitanDamage", "CritDamage", "CritDamagePerSeasonDay", "DamagePerSoloRaidWorld", "DamagePerRunningActiveSkill", "DamagePerOwnedCardLevel", "DamagePerEventSet", "DamagePerEquipmentSet", "AllDamagePerSeasonDay", "LegacyPetDamageEffect", "ExoticPetDamageEffect", "SlashBoost", "AllArtifactDamageEffect", "HSArtifactDamage", "DamagePerOwnedArtifact"}:
        return 1.0
    if bonus == "PrestigeRelic":
        return None  # BoS is a farming decision, not immediate pushing power.
    return None


def log_sum(values):
    """log10(sum(10**x)), including huge imported levels."""
    values = list(values)
    if not values:
        return 0.0
    largest = max(values)
    return largest + math.log10(sum(10 ** (v - largest) for v in values))


def item_effect_gain(item, level, enchanted=False):
    """Log10 of the next-rank log10 multiplier gain for 1 + c*L**g.

    Finite differences at ordinary levels; a stable local derivative beyond
    1e12, where adding one in binary floats cannot resolve the effect ratio.
    EnchantmentMult scales c once; discovery/enchanting costs are not upgrades.
    """
    ln_level = float(level.log10())
    g = float(item["GrowthExpo"])
    c = float(item["EffectPerLevel"])
    if c <= 0 or g <= 0:
        return None
    magnitude = log(c) + g * ln_level
    if enchanted:
        magnitude += log(item["EnchantmentMult"])
    # fraction of total effect contributed by the scalable term, in log space.
    log_fraction = -math.log10(1 + 10 ** -magnitude) if magnitude >= 0 else magnitude - math.log10(1 + 10 ** magnitude)
    if ln_level > 12:
        return log(g / math.log(10)) + log_fraction - ln_level
    delta = g * math.log1p(1 / float(level))
    # Stable finite log-ratio, even when the effect itself exceeds float range.
    fraction = 10 ** log_fraction
    if delta > 600:
        gain = (log_fraction * math.log(10) + delta) / math.log(10)
    else:
        gain = math.log1p(fraction * math.expm1(delta)) / math.log(10)
    return log(gain) if gain > 0 else None


def scientific_from_log(value):
    exponent = math.floor(value)
    return f"{10 ** (value - exponent):.3f}e{exponent:+d}"


def rank_items(player, settings, kind="artifacts"):
    """Finite next-level gains per modeled cost, not a full spending plan.

    1+c*L**g effect and C*L**p cost model. Monument growth and cost use their
    own CSV parameters. Conditional factors remain fixed. Includes additive
    collection damage; unknown secondary effects are never invented.
    """
    if kind not in {"artifacts", "monuments"}:
        raise ValueError("Unsupported collection.")
    owned = player.artifacts if kind == "artifacts" else player.monuments
    balance = player.relics if kind == "artifacts" else player.mementos
    # Every owned item adds damage to its collection, including off-build items.
    # Seasonal collection damage has its own exponent in the snapshot.
    contributions = {}
    for key, level in owned.items():
        item = catalog()[kind].get(key)
        if item and level > 0 and (kind == "artifacts" or item["IsActive"] == "TRUE"):
            if float(item["DamageBonus"]) > 0:
                exponent = float(item.get("DamageExpo", 1))
                contributions[key] = log(item["DamageBonus"]) + exponent * float(level.log10())
    total_damage = log_sum([0.0, *contributions.values()])
    rows = []
    for key, level in owned.items():
        item = catalog()[kind].get(key)
        row = {"ID": key, "Name": item["Name"] if item else key, "Level": str(level), "Effect": item["BonusType"] if item else "Unknown",
               "Status": "Unknown ID", "Priority": None, "log_efficiency": None,
               "Next cost (estimate)": None, "Affordable": None, "Gain log10 (estimate)": None,
               "Primary gain log10 (estimate)": None, "Collection gain log10 (estimate)": None,
               "Effect description": catalog()["bonuses"].get(item["BonusType"] if item else "", {}).get("Description", "Unknown effect"),
               "Enchanted": key in (player.enchanted if kind == "artifacts" else player.monument_enchanted)}
        if item:
            active = kind != "monuments" or item["IsActive"] == "TRUE"
            cap = int(item["MaxLevel"])
            weight = bonus_weight(item["BonusType"], settings)
            row["Status"] = "Not owned" if not level else "Inactive in snapshot" if not active else "Maxed" if cap and level >= cap else "Farming / BoS" if key == "Artifact22" else "Effect not modeled; collection damage only" if weight is None else "Other build; collection damage only" if weight == 0 else "Ranked (estimate)"
            if level and active and not (cap and level >= cap) and key != "Artifact22":
                ln_level = float(level.log10())
                gains = []
                effect_gain = item_effect_gain(item, level, row["Enchanted"])
                if weight is not None:
                    row["Primary gain log10 (estimate)"] = "0"
                if weight is not None and weight > 0 and effect_gain is not None:
                    primary_gain = log(weight) + effect_gain
                    gains.append(primary_gain)
                    row["Primary gain log10 (estimate)"] = scientific_from_log(primary_gain)
                if key in contributions:
                    exponent = float(item.get("DamageExpo", 1))
                    share = contributions[key] - total_damage
                    if ln_level > 12:
                        collection_gain = log(exponent / math.log(10)) + share - ln_level
                        gains.append(collection_gain)
                        row["Collection gain log10 (estimate)"] = scientific_from_log(collection_gain)
                    else:
                        delta = exponent * math.log1p(1 / float(level))
                        gain = math.log1p(10 ** share * math.expm1(delta)) / math.log(10)
                        if gain > 0:
                            gains.append(log(gain))
                            row["Collection gain log10 (estimate)"] = scientific_from_log(log(gain))
                cost = log(item["CostCoef"]) + float(item["CostExpo"]) * ln_level
                row["Next cost (estimate)"] = scientific_from_log(cost)
                row["Affordable"] = None if balance is None else balance > 0 and cost <= float(balance.log10())
                if gains:
                    combined = log_sum(gains)
                    row["Gain log10 (estimate)"] = scientific_from_log(combined)
                    row["log_efficiency"] = combined - cost
        rows.append(row)
    rows.sort(key=lambda r: (r["log_efficiency"] is None, -(r["log_efficiency"] or 0), r["Name"]))
    for index, row in enumerate((r for r in rows if r["log_efficiency"] is not None), 1):
        row["Priority"] = index
    best = next((r["log_efficiency"] for r in rows if r["Priority"] == 1), None)
    for row in rows:
        row["Relative efficiency %"] = None if row["log_efficiency"] is None else round(100 * 10 ** (row["log_efficiency"] - best), 2)
    return rows
