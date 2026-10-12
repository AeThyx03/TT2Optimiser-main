"""Compare independent in-game purchases with the monument cost model."""
import json
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.tt2_data import catalog


def measured_session_check(gold_weight=.7, active_spells=4):
    """Independent batch evidence; never promote a local fit to a global law.

    Fit a geometric price sequence from each initial single/batch quote, then
    check its following quote, which was not used in fitting. Compare measured
    primary and aggregate shared gains at the actual purchase sequence.
    """
    evidence = json.loads((Path(__file__).resolve().parents[1] / "data/tt2/monument_validation_observations.json").read_text())
    session = evidence["upgrade_session"]
    rows = []
    for record in session["purchases"]:
        count = record["levels_bought"]
        ratio = float(Decimal(record["batch_price"]) / Decimal(record["next_level_price"]))
        def series(rate, n):
            return math.expm1(rate * n) / math.expm1(rate) if rate else float(n)
        lo, hi = 0.0, .01
        for _ in range(80):
            mid = (lo + hi) / 2
            if series(mid, count) < ratio:
                lo = mid
            else:
                hi = mid
        rate = (lo + hi) / 2
        following_ratio = float(Decimal(record["following_quote_price"]) / Decimal(record["next_level_price"]))
        predicted = math.exp(rate * count) * series(rate, record["following_quote_levels"])
        primary = float(Decimal(record["primary_after"]).log10() - Decimal(record["primary_before"]).log10())
        shared = float(Decimal(record["pool_after_percent"]).log10() - Decimal(record["pool_before_percent"]).log10())
        weight = gold_weight * active_spells if record["monument"] == "SeasonalArtifact51" else 1.0
        gain = shared + weight * primary
        rows.append({"monument": record["monument"], "levels_bought": count,
                     "cost": record["batch_price"], "gain_log10": gain,
                     "primary_gain_log10": primary, "pool_gain_log10": shared,
                     "local_price_growth_per_level": math.expm1(rate),
                     "held_out_quote_relative_error": predicted / following_ratio - 1,
                     "log_efficiency": math.log10(gain) - float(Decimal(record["batch_price"]).log10())})
    return {"purchases": rows,
            "glassbone_to_hierophant_efficiency": 10 ** (rows[0]["log_efficiency"] - rows[1]["log_efficiency"]),
            "export_mementos_changed": session["export_mementos_before"] != session["export_mementos_after"],
            "global_cost_model_validated": False, "limitations": session["limitations"]}


def supplied_screenshot_check():
    evidence = json.loads((Path(__file__).resolve().parents[1] / "data/tt2/monument_validation_observations.json").read_text())
    h, g = evidence["observations"][:2]
    items = catalog()["monuments"]
    def investment(record, level):
        item = items[record["monument"]]
        power = float(item["CostExpo"]) + 1
        return float(item["CostCoef"]) / power * level ** power
    observed = g["lifetime_share_percent"] / h["lifetime_share_percent"]
    modeled = investment(g, g["level_display"]) / investment(h, h["level_display"])
    # Allow a full 10 levels either way for K-display truncation/rounding.
    model_max = investment(g, g["level_display"] + 10) / investment(h, h["level_display"] - 10)
    observed_min = (g["lifetime_share_percent"] - .005) / (h["lifetime_share_percent"] + .005)
    checks = []
    for record in (h, g):
        item = items[record["monument"]]
        measured_gain = float(Decimal(record["next_damage_percent"]).log10() - Decimal(record["damage_percent"]).log10())
        level = record["level_display"]
        predicted_gain = math.log10(float(item["DamageBonus"])) * ((level + 1) ** float(item["DamageExpo"]) - level ** float(item["DamageExpo"]))
        checks.append({"Monument": item["Name"], "Observed next-level damage gain log10": measured_gain,
                       "Predicted next-level damage gain log10": predicted_gain})
    return {"observed_investment_ratio": observed, "modeled_investment_ratio": modeled,
            "contradicted_even_with_rounding": observed_min > model_max,
            "shared_damage_checks": checks, "missing": evidence["missing"]}


def validate_purchases(payload):
    """Check relative cost scaling without treating a fitted scale as proof.

    Mementos spent must be measured, not reconstructed from predicted costs.
    A common absolute multiplier cancels from pairwise cost comparisons.
    """
    try:
        observations = json.loads(payload)
    except (ValueError, TypeError) as exc:
        raise ValueError("Paste a JSON array of measured upgrades.") from exc
    if not isinstance(observations, list) or not 1 <= len(observations) <= 100:
        raise ValueError("Provide between 1 and 100 measured upgrades.")
    items = catalog()["monuments"]
    names = {item["Name"].casefold(): key for key, item in items.items()}
    rows = []
    seen = set()
    for record in observations:
        try:
            key = record["monument"]
            key = key if key in items else names.get(key.casefold())
            before, after, spent = (Decimal(str(record[field])) for field in ("level_before", "level_after", "mementos_spent"))
            if not key or not all(v.is_finite() and v > 0 for v in (before, after, spent)):
                raise ValueError()
            if before != int(before) or after != int(after) or after <= before or after > 10 ** 12:
                raise ValueError()
            if (key, before, after) in seen:
                raise ValueError()
            item = items[key]
            if int(item["MaxLevel"]) and after > int(item["MaxLevel"]):
                raise ValueError()
            seen.add((key, before, after))
        except (KeyError, AttributeError, TypeError, ValueError, InvalidOperation, OverflowError) as exc:
            raise ValueError("Each observation needs a known monument, distinct whole levels (1–1e12), and positive mementos spent. Do not duplicate a purchase.") from exc
        exponent, coefficient = float(item["CostExpo"]), float(item["CostCoef"])
        start, end = int(before), int(after)
        if end - start <= 10000:
            relative_cost = coefficient * math.fsum(level ** exponent for level in range(start, end))
        else:
            # Midpoint integral approximates the discrete sum for large batches.
            relative_cost = coefficient * ((end - .5) ** (exponent + 1) - (start - .5) ** (exponent + 1)) / (exponent + 1)
        row = {"Monument": item["Name"], "From": start, "To": end,
               "Mementos spent": str(spent), "Cost scale log10": float(spent.log10()) - math.log10(relative_cost),
               "Shared damage check": "Not supplied"}
        supplied = [field in record for field in ("damage_before_percent", "damage_after_percent")]
        if any(supplied):
            if not all(supplied):
                raise ValueError("Supply both before and after All Monument Damage percentages.")
            try:
                damage = [Decimal(str(record[field])) for field in ("damage_before_percent", "damage_after_percent")]
                if not all(v.is_finite() and v > 0 for v in damage):
                    raise ValueError()
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise ValueError("Damage percentages must be positive scientific-notation numbers.") from exc
            predicted = [2 + math.log10(float(item["DamageBonus"])) * level ** float(item["DamageExpo"]) for level in (start, end)]
            error = max(abs(float(v.log10()) - estimate) for v, estimate in zip(damage, predicted))
            row["Shared damage error log10"] = round(error, 4)
            row["Shared damage check"] = "Matches within display rounding" if error <= .02 else "Mismatch — investigate season/formula"
        rows.append(row)
    scales = [row["Cost scale log10"] for row in rows]
    spread = max(scales) - min(scales)
    monuments = {row["Monument"] for row in rows}
    repeated = all(sum(row["Monument"] == name for row in rows) >= 2 for name in monuments)
    sufficient = len(monuments) >= 2 and repeated
    verdict = "Need two purchases each for at least two monuments" if not sufficient else (
        "Relative costs agree within 5% over the measured range" if spread <= math.log10(1.05)
        else "Relative cost model fails the 5% agreement check")
    return {"rows": rows, "verdict": verdict, "cost_scale_spread_log10": spread,
            "sufficient": sufficient, "costs_match": sufficient and spread <= math.log10(1.05)}
