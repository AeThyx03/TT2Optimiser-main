import json
import unittest
import math
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


from src.tt2_data import BUILDS, GOLD_SOURCES, catalog
from src.tt2_optimizer import Settings, bonus_weight, item_effect_gain, monument_lifetime_targets, monument_experimental_targets, monument_weight, optimize_skills, qol_score, rank_items, skill_score, spent, validate_allocation
from src.tt2_player import ImportError, parse_player

DEMO = Path(__file__).resolve().parents[1] / "examples/player-demo.json"


def api_player(**kwargs):
    return {"name": "Tester", "total_skill_points": "500", "max_stage": 100000,
            "skill_tree": [{"skill_id": "AllHelperDmg", "level": 2}, {"skill_id": "ClanShipDmg", "level": 1}], **kwargs}


class ImportTests(unittest.TestCase):
    def test_game_export_and_actual_cost(self):
        p = parse_player(DEMO.read_text())
        # Level two costs Co0 + Co1 = 1 + 2, not just its current rank's price.
        self.assertEqual(p.spent_sp, 4)
        self.assertEqual(p.available_sp, 1496)
        self.assertEqual(p.relics, Decimal("1.25e40"))

    def test_api_shape_and_wrappers(self):
        p = parse_player({"data": api_player(artifacts=[{"artifact_id": "Artifact22", "level": "1e1000", "is_enchanted": True}])})
        self.assertEqual(p.spent_sp, 4)
        self.assertEqual(p.artifacts["Artifact22"], Decimal("1e1000"))
        self.assertIn("Artifact22", p.enchanted)

    def test_received_minus_spent_is_exact(self):
        p = parse_player(api_player(relics_received="10000000000000000000000000000000000000001", relics_spent="10000000000000000000000000000000000000000"))
        self.assertEqual(p.relics, 1)

    def test_rejects_invalid_payloads(self):
        for raw in ("{oops", "[]", "{}", '{"total_skill_points":2,"total_skill_points":3}'):
            with self.subTest(raw=raw), self.assertRaises(ImportError):
                parse_player(raw)

    def test_rejects_invalid_sp(self):
        for value in (-1, "NaN", "Infinity", "3.2", True, 200001):
            with self.subTest(value=value), self.assertRaises(ImportError):
                parse_player(api_player(total_skill_points=value))

    def test_unknown_allocated_skill_fails_closed(self):
        with self.assertRaisesRegex(ImportError, "Unknown allocated"):
            parse_player(api_player(skill_tree=[{"skill_id": "FutureSkill", "level": 1}]))

    def test_overcap_and_overspent(self):
        with self.assertRaises(ImportError):
            parse_player(api_player(skill_tree=[{"skill_id": "TapDmg", "level": 1000}]))
        with self.assertRaises(ImportError):
            parse_player(api_player(total_skill_points=3))

    def test_unknown_artifacts_retained_and_warned(self):
        p = parse_player(api_player(artifacts={"Future": "1e400"}))
        self.assertIn("Future", p.artifacts)
        self.assertTrue(p.warnings)

    def test_missing_skill_tree_is_unknown(self):
        raw = api_player()
        del raw["skill_tree"]
        p = parse_player(raw)
        self.assertFalse(p.skills_known)
        with self.assertRaisesRegex(ValueError, "current skill tree"):
            optimize_skills(p, mode="spend")

    def test_missing_budget_is_not_invented(self):
        with self.assertRaisesRegex(ImportError, "Missing total"):
            parse_player({"skillTree": {"TapDmg": 1}})

    def test_missing_currency_is_unknown(self):
        self.assertIsNone(parse_player(api_player()).relics)

    def test_negative_balance_rejected(self):
        with self.assertRaises(ImportError):
            parse_player(api_player(relics_received="1", relics_spent="2"))

    def test_version_warning(self):
        p = parse_player(api_player(version="99.0.0"))
        self.assertTrue(any("differs" in x for x in p.warnings))


class SkillTests(unittest.TestCase):
    def test_optimization_goal_validation_and_legacy_qol(self):
        self.assertEqual(Settings().goal, "push")
        self.assertEqual(Settings(qol=True).goal, "balanced")
        self.assertEqual(Settings(qol=True, optimization_goal="push").objective_weights, (1, 0))
        self.assertEqual(Settings(optimization_goal="speed").effective_lightning_attempts, 3)
        self.assertEqual(Settings(optimization_goal="balanced").effective_lightning_attempts, 15)
        self.assertEqual(Settings(optimization_goal="speed", lightning_attempts=20).effective_lightning_attempts, 20)
        with self.assertRaisesRegex(ValueError, "push, speed or balanced"):
            Settings(optimization_goal="fastest")

    def test_goals_change_allocation_and_report_objective_correctly(self):
        p = parse_player(DEMO.read_text())
        results = {g: optimize_skills(p, Settings(build="Heavenly Strike", optimization_goal=g), reserve=10)
                   for g in ("push", "speed", "balanced")}
        self.assertEqual(len({json.dumps(r["levels"], sort_keys=True) for r in results.values()}), 3)
        self.assertGreater(results["push"]["log_gain"], results["balanced"]["log_gain"])
        self.assertGreater(results["balanced"]["log_gain"], results["speed"]["log_gain"])
        self.assertGreater(results["speed"]["utility_gain"], results["balanced"]["utility_gain"])
        self.assertEqual(results["push"]["utility_gain"], 0)
        for goal, r in results.items():
            self.assertEqual(r["optimization_goal"], goal)
            d, u = r["objective_weights"]
            self.assertAlmostEqual(r["objective_gain"], d*r["log_gain"] + u*r["utility_gain"])
            self.assertAlmostEqual(sum(r["speed_components"].values()), r["utility_gain"])
            self.assertLessEqual(r["spent"], p.total_sp-10)
            self.assertFalse(validate_allocation(r["levels"], p.max_stage))

    def test_speed_goals_preserve_owned_ranks_for_every_build(self):
        p = parse_player(api_player(total_skill_points=300))
        for build in BUILDS:
            for goal in ("speed", "balanced"):
                with self.subTest(build=build, goal=goal):
                    r = optimize_skills(p, Settings(build=build, optimization_goal=goal), "spend", reserve=10)
                    self.assertLessEqual(r["spent"], 290)
                    self.assertFalse(validate_allocation(r["levels"], p.max_stage))
                    for key, rank in p.skills.items():
                        self.assertGreaterEqual(r["levels"][key], rank)

    def test_extra_speed_effects_route_to_the_correct_build_and_gold(self):
        sc = Settings(build="Shadow Clone", optimization_goal="speed")
        hs = Settings(build="Heavenly Strike", optimization_goal="speed")
        self.assertGreater(qol_score("CloneDmg", 5, sc), 0)
        self.assertEqual(qol_score("CloneDmg", 5, hs), 0)
        self.assertGreater(qol_score("ExplosivesExpert", 5, Settings(build="Gold Gun", optimization_goal="speed")), 0)
        self.assertEqual(qol_score("ExplosivesExpert", 5, hs), 0)
        self.assertEqual(qol_score("PetGoldQTE", 20, hs), 0)
        self.assertGreater(qol_score("PetGoldQTE", 20, Settings(gold="Heart of Gold", optimization_goal="speed")), 0)

    def test_qol_routes_utility_without_changing_damage_score(self):
        for build in BUILDS:
            on, off = Settings(build=build, qol=True), Settings(build=build)
            self.assertEqual(qol_score("Cloaking", 4, off), 0)
            self.assertGreater(qol_score("Cloaking", 4, on), 0)
            self.assertGreater(qol_score("MPCapacityBoost", 4, on), 0)
            self.assertEqual(qol_score("TapDmg", 4, on), 0)
            self.assertEqual(skill_score("ClanShipDmg", 4, on, set()), skill_score("ClanShipDmg", 4, off, set()))
            self.assertEqual(qol_score("CloneSkillBoost", 4, on) > 0, build == "Shadow Clone")
            self.assertEqual(qol_score("BurstSkillMana", 4, on) > 0, build == "Heavenly Strike")

    def test_qol_plans_respect_budget_prerequisites_and_owned_skills(self):
        p = parse_player(DEMO.read_text())
        for build in BUILDS:
            for mode in ("respec", "spend"):
                with self.subTest(build=build, mode=mode):
                    result = optimize_skills(p, Settings(build=build, qol=True), mode, reserve=10)
                    self.assertLessEqual(result["spent"], p.total_sp - 10)
                    self.assertFalse(validate_allocation(result["levels"], p.max_stage))
                    self.assertAlmostEqual(result["objective_gain"], result["log_gain"] + result["utility_gain"])
                    self.assertGreater(result["utility_gain"], 0)
                    if mode == "spend":
                        for key, rank in p.skills.items():
                            self.assertGreaterEqual(result["levels"][key], rank)
        baseline = optimize_skills(p)
        enabled = optimize_skills(p, Settings(qol=True))
        self.assertEqual(baseline, optimize_skills(p, Settings(qol=False)))
        self.assertNotEqual(baseline["levels"], enabled["levels"])
        self.assertGreater(enabled["levels"].get("Cloaking", 0), baseline["levels"].get("Cloaking", 0))

    def test_all_build_gold_combinations_budget_and_prerequisites(self):
        p = parse_player(api_player(total_skill_points=300))
        plans = set()
        for build in BUILDS:
            for gold in GOLD_SOURCES:
                with self.subTest(build=build, gold=gold):
                    result = optimize_skills(p, Settings(build, gold), reserve=10)
                    self.assertLessEqual(result["spent"], 290)
                    self.assertEqual(result["spent"] + result["remaining"], 300)
                    self.assertFalse(validate_allocation(result["levels"], p.max_stage))
                    self.assertEqual(sum(step["SP"] for step in result["steps"]), result["spent"])
                    plans.add(json.dumps(result["levels"], sort_keys=True))
        self.assertGreater(len(plans), 12)

    def test_spend_never_removes_owned_levels(self):
        p = parse_player(api_player())
        r = optimize_skills(p, mode="spend", reserve=5)
        for k, v in p.skills.items():
            self.assertGreaterEqual(r["levels"][k], v)
        self.assertLessEqual(r["spent"], 495)

    def test_zero_and_tiny_budgets(self):
        for budget in range(5):
            p = parse_player(api_player(total_skill_points=budget, skill_tree=[]))
            r = optimize_skills(p)
            self.assertLessEqual(r["spent"], budget)
            self.assertFalse(validate_allocation(r["levels"], p.max_stage))

    def test_stage_locks(self):
        p = parse_player(api_player(max_stage=0, skill_tree=[]))
        r = optimize_skills(p)
        self.assertTrue(all(catalog()["skills"][k]["TierNum"] == "1" for k in r["levels"]))

    def test_child_cannot_fund_own_tier_unlock(self):
        self.assertTrue(validate_allocation({"AllHelperDmg": 1, "ClanShipDmg": 20}, 100000))

    def test_invalid_existing_tree_rejected_in_spend_mode(self):
        p = parse_player(api_player(skill_tree=[{"skill_id": "ClanShipDmg", "level": 1}]))
        with self.assertRaisesRegex(ValueError, "Current tree"):
            optimize_skills(p, mode="spend")

    def test_gold_routing(self):
        self.assertGreater(skill_score("FairyGold", 1, Settings(gold="Fairy"), set()), 0)
        self.assertEqual(skill_score("FairyGold", 1, Settings(gold="Heart of Gold"), set()), 0)
        self.assertEqual(skill_score("TapDmg", 20, Settings(build="Clan Ship"), set()), 0)

    def test_multicast_equipment_changes_score(self):
        s = Settings(build="Clan Ship")
        self.assertGreater(skill_score("HelperBoostMultiCastSkill", 1, s, {"MultiCast"}), skill_score("HelperBoostMultiCastSkill", 1, s, set()))

    def test_pet_mythic_contributes_per_point(self):
        s = Settings(build="Pet")
        self.assertGreater(skill_score("PetDmg", 2, s, {"FireKnight"}), skill_score("PetDmg", 2, s, set()))

    def test_deterministic_export(self):
        p = parse_player(api_player())
        a, b = optimize_skills(p), optimize_skills(p)
        self.assertEqual(a, b)
        self.assertEqual(set(a["export"]), {"Version", "Skills"})
        self.assertEqual(spent(a["export"]["Skills"]), a["spent"])

    def test_contracts_excluded_by_default(self):
        p = parse_player(api_player(total_skill_points=3000))
        r = optimize_skills(p)
        self.assertFalse({"ForbiddenContract", "RoyalContract", "TerrifyingPact"} & r["levels"].keys())


class ItemTests(unittest.TestCase):
    def test_rosabella_identity_and_heavenly_strike_relevance(self):
        monuments = catalog()["monuments"]
        self.assertEqual(monuments["SeasonalArtifact6"]["Name"], "Rosabella's Village")
        self.assertEqual(monuments["SeasonalArtifact6"]["BonusType"], "DeadlyDamageCompanion")
        self.assertEqual(monuments["SeasonalArtifact27"]["Name"], "Mound of Brothers' Meet")
        for identifier in ("Rosabella's Village", "SeasonalArtifact6"):
            with self.subTest(identifier=identifier):
                p = parse_player(api_player(monuments={identifier: 93000, "SeasonalArtifact43": 93000}))
                self.assertIn("SeasonalArtifact6", p.monuments)
                rows = rank_items(p, Settings(build="Heavenly Strike"), "monuments")
                rosabella = next(r for r in rows if r["ID"] == "SeasonalArtifact6")
                self.assertEqual(rosabella["Primary gain log10 (estimate)"], "0")
                self.assertIsNone(rosabella["Priority"])
                self.assertIsNone(rosabella["Gain log10 (estimate)"])
                self.assertIsNone(rosabella["Collection gain log10 (estimate)"])
                self.assertIn("Not recommended", rosabella["Status"])
                self.assertEqual(rows[0]["ID"], "SeasonalArtifact43")
                self.assertIsNone(rows[0]["Priority"])
                self.assertGreater(rows[0]["Target lifetime mementos % (estimate)"], 0)

    def test_companion_deadly_damage_build_matrix(self):
        p = parse_player(api_player(monuments={"SeasonalArtifact6": 93000}))
        for build in BUILDS:
            with self.subTest(build=build):
                expected = build in {"Pet", "Clan Ship", "Shadow Clone"}
                self.assertEqual(bonus_weight("DeadlyDamageCompanion", Settings(build=build)), float(expected))
                row = rank_items(p, Settings(build=build), "monuments")[0]
                self.assertEqual(row["Primary gain log10 (estimate)"] == "0", not expected)

    def test_finite_effect_gain_and_enchantment(self):
        item = {"EffectPerLevel": ".5", "GrowthExpo": "2", "EnchantmentMult": "100"}
        expected = math.log10((1 + .5 * 11**2) / (1 + .5 * 10**2))
        self.assertAlmostEqual(10 ** item_effect_gain(item, Decimal(10)), expected)
        enchanted = math.log10((1 + 50 * 11**2) / (1 + 50 * 10**2))
        self.assertAlmostEqual(10 ** item_effect_gain(item, Decimal(10), True), enchanted)
        self.assertTrue(math.isfinite(item_effect_gain(item, Decimal('1e1000'))))

    def test_collection_damage_and_affordability(self):
        p = parse_player(api_player(artifacts={"Artifact20": 10, "Artifact30": 10}, relics=0))
        rows = rank_items(p, Settings(build="Clan Ship"))
        self.assertTrue(all(row["Affordable"] is False for row in rows))
        self.assertEqual(rows[0]["Relative efficiency %"], 100)
        self.assertTrue(all(row["log_efficiency"] is not None for row in rows))
        p.relics = Decimal('1e100')
        self.assertTrue(all(row["Affordable"] is True for row in rank_items(p, Settings())))

    def test_primary_fallback_uses_growth_weights_without_cost_inference(self):
        # Weighted primary growth 4:12 supplies a provisional 25:75 split.
        # It must not infer a spending budget from levels or balances.
        p = parse_player(api_player())
        p.monuments = {"damage": Decimal(100), "gold": Decimal(1000),
                       "offbuild": Decimal(20), "capped": Decimal(40), "unknown": Decimal(5)}
        base = {"IsActive": "TRUE", "MaxLevel": "0", "PrimaryModelAvailable": True,
                "EffectPerLevel": "1", "CostExpo": "1", "GrowthExpo": "4"}
        items = {"damage": dict(base, BonusType="AllDamage", CostCoef="1"),
                 "gold": dict(base, BonusType="GoldAll", GrowthExpo="12", CostCoef="1e70"),
                 "offbuild": dict(base, BonusType="CompanionDamage"),
                 "capped": dict(base, BonusType="AllDamage", MaxLevel="40")}
        with patch("src.tt2_optimizer.catalog", return_value={"monuments": items}):
            targets = monument_lifetime_targets(p, Settings(build="Heavenly Strike", gold_weight=1))
            self.assertEqual(targets, {"damage": 25, "gold": 75, "offbuild": 0, "capped": 0, "unknown": None})
            p.monuments["damage"] = Decimal('1e1000')
            p.mementos = Decimal('1e500')
            self.assertEqual(targets, monument_lifetime_targets(p, Settings(build="Heavenly Strike", gold_weight=1)))

    def test_lifetime_targets_use_actual_build_and_sum_to_100(self):
        p = parse_player((Path(__file__).parent / "fixtures/monument-player.json").read_text())
        targets = monument_experimental_targets(p, Settings(build="Heavenly Strike"))
        self.assertAlmostEqual(sum(v for v in targets.values() if v is not None), 100)
        self.assertEqual(targets["SeasonalArtifact6"], 0)
        self.assertGreater(targets["SeasonalArtifact51"], 0)
        self.assertLess(targets["SeasonalArtifact51"], 100)
        self.assertGreater(targets["SeasonalArtifact43"], 0)
        # Turning off gold reduces every gold-only allocation to zero.
        damage_only = monument_experimental_targets(p, Settings(build="Heavenly Strike", gold_weight=0))
        self.assertEqual(damage_only["SeasonalArtifact51"], 0)
        self.assertGreater(damage_only["SeasonalArtifact43"], targets["SeasonalArtifact43"])
        lone = parse_player(api_player(monuments={"Rosabella's Village": 1}))
        self.assertIsNone(monument_lifetime_targets(lone, Settings(build="Heavenly Strike"))["SeasonalArtifact6"])

    def test_enchantment_aliases_in_both_collections(self):
        data = api_player(artifacts={"Book of Prophecy": {"level": 1, "enchanted": True}},
                          monuments={"Skull Island": {"level": 1, "enchanted": True}})
        p = parse_player(data)
        self.assertIn("Artifact20", p.enchanted)
        self.assertIn("SeasonalArtifact1", p.monument_enchanted)
        self.assertTrue(rank_items(p, Settings(), "monuments")[0]["Enchanted"])

    def test_huge_levels_and_relevance(self):
        p = parse_player(api_player(artifacts={"Artifact30": "1e1000", "Artifact38": 30, "Future": 1}))
        rows = {r["ID"]: r for r in rank_items(p, Settings())}
        self.assertIsNotNone(rows["Artifact30"]["Priority"])
        self.assertIsNone(rows["Artifact38"]["Priority"])
        self.assertEqual(rows["Future"]["Status"], "Unknown ID")

    def test_bos_and_caps_not_ranked(self):
        p = parse_player(api_player(artifacts={"Artifact22": 500, "Artifact50": 1000000}))
        rows = rank_items(p, Settings())
        self.assertTrue(all(r["Priority"] is None for r in rows))

    def test_monument_build_changes_priority(self):
        p = parse_player(api_player(seasonal_artifacts=[{"artifact_id": "SeasonalArtifact31", "level": 10}]))
        self.assertGreater(rank_items(p, Settings(), "monuments")[0]["Target lifetime mementos % (estimate)"], 0)
        cs = rank_items(p, Settings(), "monuments")[0]
        pet = rank_items(p, Settings(build="Pet"), "monuments")[0]
        self.assertIn("Not recommended", pet["Status"])
        self.assertIsNone(pet["Priority"])
        self.assertIsNone(cs["log_efficiency"])
        self.assertGreater(cs["Target lifetime mementos % (estimate)"], 0)

    def test_low_level_off_build_monuments_cannot_win(self):
        # Reproduce the screenshot imbalance: useful monuments ~110-125k;
        # off-build monuments ~32k, previously favored by collection/cost.
        p = parse_player(api_player(monuments={
            "Rosabella's Village": 32230, "Hideout of Stratagem": 32490,
            "Three Cup Mana Pool": 32030, "Lost Cups Five": 77580,
            "Sword Master's Shrine": 77640, "Hierophant's Library": 125030,
            "Nine Pentacle Garden": 110060, "Emblem of Worlds": 110060,
            "Midnight Pass": 110060}))
        for gold in GOLD_SOURCES:
            rows = rank_items(p, Settings(build="Heavenly Strike", gold=gold), "monuments")
            by_id = {r["ID"]: r for r in rows}
            for key in ("SeasonalArtifact6", "SeasonalArtifact31", "SeasonalArtifact42", "SeasonalArtifact41", "SeasonalArtifact18"):
                self.assertIsNone(by_id[key]["Priority"])
            self.assertIn(rows[0]["ID"], {"SeasonalArtifact43", "SeasonalArtifact35", "SeasonalArtifact36", "SeasonalArtifact32"})
        lone = parse_player(api_player(monuments={"Rosabella's Village": 1}))
        self.assertIsNone(rank_items(lone, Settings(build="Heavenly Strike"), "monuments")[0]["Priority"])

    def test_screenshot_effects_caps_and_parameter_mismatch(self):
        monuments = catalog()["monuments"]
        self.assertEqual(monuments["SeasonalArtifact27"]["BonusType"], "AllArtifactDamageEffect")
        self.assertEqual(monuments["SeasonalArtifact37"]["BonusType"], "AllActiveSkillAmount")
        self.assertEqual(monuments["SeasonalArtifact45"]["BonusType"], "TwilightBoost")
        self.assertEqual(monuments["SeasonalArtifact54"]["MaxLevel"], "40")
        self.assertEqual(monuments["SeasonalArtifact52"]["MaxLevel"], "40")
        p = parse_player(api_player(monuments={"Heartbloom Grove": 110060,
                                               "The Scarred Constellation": 40,
                                               "The Clocksout Engine": 40}))
        rows = {r["ID"]: r for r in rank_items(p, Settings(build="Heavenly Strike"), "monuments")}
        self.assertEqual(rows["SeasonalArtifact45"]["Status"], "Primary allocation estimate")
        self.assertIsNone(rows["SeasonalArtifact45"]["Priority"])
        self.assertGreater(rows["SeasonalArtifact45"]["Target lifetime mementos % (estimate)"], 0)
        self.assertEqual(rows["SeasonalArtifact54"]["Status"], "Maxed")
        self.assertEqual(rows["SeasonalArtifact52"]["Status"], "Maxed")

    def test_screenshot_effect_routing(self):
        self.assertEqual(bonus_weight("SwordAttackDamage", Settings(build="Shadow Clone")), 1)
        self.assertEqual(bonus_weight("BoostedSwordAttackDamage", Settings(build="Clan Ship")), 2)
        self.assertEqual(bonus_weight("GoldSpecialty", Settings(gold="Chesterson")), 0)
        self.assertEqual(bonus_weight("ShadowCloneAllSkillBoost", Settings(build="Heavenly Strike")), 0)

    def test_actual_export_monument_regression(self):
        p = parse_player((Path(__file__).parent / "fixtures/monument-player.json").read_text())
        rows = rank_items(p, Settings(build="Heavenly Strike"), "monuments")
        rosabella = next(r for r in rows if r["ID"] == "SeasonalArtifact6")
        self.assertEqual(rosabella["Name"], "Rosabella's Village")
        self.assertIsNone(rosabella["Priority"])
        self.assertEqual(rosabella["Primary gain log10 (estimate)"], "0")
        self.assertIsNone(rosabella["Next cost (estimate)"])
        self.assertIsNone(rosabella["Affordable"])
        self.assertIn("SeasonalArtifact25", p.monument_enchanted)
        self.assertNotIn("SeasonalArtifact6", p.monument_enchanted)
        self.assertEqual(len(rows), 33)
        self.assertTrue(all(r["Status"] != "Inactive in snapshot" for r in rows))
        self.assertEqual(rows[0]["ID"], "SeasonalArtifact43")
        damage_only = rank_items(p, Settings(build="Heavenly Strike", gold_weight=0), "monuments")
        self.assertEqual(damage_only[0]["ID"], "SeasonalArtifact43")

    def test_primary_fallback_rejects_unverified_concentration(self):
        p = parse_player((Path(__file__).parent / "fixtures/monument-player.json").read_text())
        settings = Settings(build="Heavenly Strike")
        targets = monument_experimental_targets(p, settings)
        self.assertAlmostEqual(sum(v for v in targets.values() if v is not None), 100)
        self.assertLess(targets["SeasonalArtifact43"], 20)
        self.assertGreater(sum(v > 0 for v in targets.values() if v is not None), 10)
        original = targets.copy()
        # Unsupported cost coefficients must not influence displayed estimates.
        items = catalog()["monuments"]
        with patch.dict(items["SeasonalArtifact43"], CostCoef="1e200", CostExpo="80"):
            self.assertEqual(original, monument_experimental_targets(p, settings))
        p.monuments["SeasonalArtifact43"] = Decimal(125220)
        p.monuments["SeasonalArtifact51"] = Decimal(126330)
        rows = {r["ID"]: r for r in rank_items(p, settings, "monuments")}
        h, g = rows["SeasonalArtifact43"], rows["SeasonalArtifact51"]
        # Glassbone dominates the additive pool in the supplied screenshots.
        self.assertIsNone(h["Collection gain log10 (estimate)"])
        self.assertGreater(float(g["Collection gain log10 (estimate)"]), .029)
        self.assertTrue(all(r["log_efficiency"] is None and r["Priority"] is None for r in rows.values()))

    def test_shared_damage_curve_matches_supplied_screenshots(self):
        # Display is percentage, hence +2. K-rounded levels allow a small
        # exponent discrepancy; these independent observations reject L^p.
        for level, base, exponent, displayed in ((40, 20, .55, 154.11),
                                                  (32030, 14, .53, 3422.428),
                                                  (77580, 14, .53, 5468.362)):
            self.assertAlmostEqual(2 + base * level ** exponent, displayed, delta=.15)

    def test_alternate_growth_matches_screenshot_magnitudes(self):
        # Check independent displayed magnitudes; level rounding and global
        # equipment bonuses omitted here can shift the leading mantissa.
        for key, level, enchanted, expected_log in (
            ("SeasonalArtifact6", 32230, False, 696.567),
            ("SeasonalArtifact36", 110060, False, 1019.272),
            ("SeasonalArtifact45", 110060, False, 651.427),
            ("SeasonalArtifact43", 125030, True, 1535.859)):
            with self.subTest(key=key):
                item = catalog()["monuments"][key]
                actual = math.log10(float(item["EffectPerLevel"])) + float(item["GrowthExpo"]) * math.log10(level)
                if enchanted:
                    actual += math.log10(float(item["EnchantmentMult"]))
                self.assertAlmostEqual(actual, expected_log, delta=.35)

    def test_active_spells_control_conditional_monuments(self):
        p = parse_player(api_player(monuments={"SeasonalArtifact28": 110100, "SeasonalArtifact51": 110100}))
        settings = Settings(build="Heavenly Strike", active_spells=("BurstDamage", "TapBoost", "HandOfMidas", "TwilightFairy"))
        portal = catalog()["monuments"]["SeasonalArtifact28"]
        self.assertEqual(monument_weight(portal, settings, p), 0)
        with_clone = Settings(build="Heavenly Strike", active_spells=("BurstDamage", "TapBoost", "HandOfMidas", "ShadowClone"))
        self.assertGreater(monument_weight(portal, with_clone, p), 0)
        menagerie = catalog()["monuments"]["SeasonalArtifact51"]
        self.assertAlmostEqual(monument_weight(menagerie, settings, p), 4 * .7)
        self.assertEqual(monument_weight(menagerie, Settings(active_spells=()), p), 0)
        with self.assertRaises(ValueError):
            Settings(active_spells=("BurstDamage", "BurstDamage"))

    def test_artifact_amplifier_uses_owned_relevant_artifacts(self):
        p = parse_player(api_player(artifacts={"Artifact30": 100, "Artifact31": 100}))
        item = catalog()["monuments"]["SeasonalArtifact27"]
        expected = sum(bonus_weight(catalog()["artifacts"][key]["BonusType"], Settings(build="Heavenly Strike")) or 0 for key in p.artifacts)
        self.assertEqual(monument_weight(item, Settings(build="Heavenly Strike"), p), expected)


if __name__ == "__main__":
    unittest.main()
