import json
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import requests

from src.tt2_api import APIError, API_URL, fetch_player
from src.tt2_data import BUILDS, GOLD_SOURCES, catalog
from src.tt2_optimizer import Settings, bonus_weight, optimize_skills, rank_items, skill_score, spent, validate_allocation
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
        p = parse_player(api_player(seasonal_artifacts=[{"artifact_id": "SeasonalArtifact10", "level": 10}]))
        self.assertEqual(rank_items(p, Settings(), "monuments")[0]["Priority"], 1)
        self.assertIsNone(rank_items(p, Settings(build="Pet"), "monuments")[0]["Priority"])


class APITests(unittest.TestCase):
    # Synthetic UUIDs, not user credentials.
    APP = "00000000-0000-4000-8000-000000000001"
    PLAYER = "00000000-0000-4000-8000-000000000002"

    def test_auth_request_and_no_redirects(self):
        request = Mock(return_value=Mock(status_code=200, json=Mock(return_value=api_player())))
        result = fetch_player(self.APP, self.PLAYER, request=request)
        self.assertIn("total_skill_points", result)
        args, kw = request.call_args
        self.assertEqual(args[0], API_URL)
        self.assertEqual(kw["headers"], {"API-Authenticate": self.APP})
        self.assertEqual(kw["json"]["player_token"], self.PLAYER)
        self.assertFalse(kw["allow_redirects"])
        self.assertNotIn("verify", kw)  # requests default remains True

    def test_rate_limit_is_local_and_single_request(self):
        state = {}
        request = Mock(return_value=Mock(status_code=429))
        with self.assertRaises(APIError):
            fetch_player(self.APP, self.PLAYER, state, request)
        with self.assertRaisesRegex(APIError, "30 seconds"):
            fetch_player(self.APP, self.PLAYER, state, request)
        self.assertEqual(request.call_count, 1)

    def test_network_errors_do_not_leak_tokens(self):
        for error in (requests.exceptions.SSLError(self.APP), requests.ConnectionError(self.PLAYER)):
            with self.subTest(error=type(error)), self.assertRaises(APIError) as ctx:
                fetch_player(self.APP, self.PLAYER, request=Mock(side_effect=error))
            self.assertNotIn(self.APP, str(ctx.exception))
            self.assertNotIn(self.PLAYER, str(ctx.exception))

    def test_invalid_token_does_not_call_network(self):
        request = Mock()
        with self.assertRaises(APIError):
            fetch_player("bad", self.PLAYER, request=request)
        request.assert_not_called()

    def test_error_payload_not_echoed(self):
        request = Mock(return_value=Mock(status_code=200, json=Mock(return_value={"_error": self.APP})))
        with self.assertRaises(APIError) as ctx:
            fetch_player(self.APP, self.PLAYER, request=request)
        self.assertNotIn(self.APP, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
