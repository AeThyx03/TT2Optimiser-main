"""Compare multiplicative monument effects and timed runs from the game."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import math
from statistics import median

from src.tt2_data import BUILDS


def log_multiplier(value):
    """Read a displayed multiplier or an explicitly signed bonus percentage."""
    text = value.strip().lower().replace(",", "")
    percent = text.endswith("%")
    if percent and not text.startswith("+"):
        raise ValueError("Use x for a multiplier or + for a bonus percentage, e.g. x1e250 or +50%.")
    try:
        number = Decimal(text[:-1] if percent else text.removeprefix("x").removesuffix("x"))
        if not number.is_finite() or number < 0 or number.adjusted() > 10000:
            raise InvalidOperation
        if percent:
            if number.adjusted() > 16:
                return float(number.log10()) - 2
            return math.log1p(float(number) / 100) / math.log(10)
        if number < 1:
            raise InvalidOperation
        return float(number.log10())
    except InvalidOperation:
        raise ValueError("Enter a multiplier of at least x1 or a nonnegative bonus, e.g. x1e250 or +50%.") from None


@dataclass(frozen=True)
class MonumentEffect:
    monument: str
    builds: tuple[str, ...]
    kind: str
    log_gain: float


def compare_monuments(effects, gold_weight):
    """Rank the recorded bonuses on a common baseline, in log10 space.

    Each contribution represents the effective multiplier on a build and must
    stack multiplicatively with other contributions in the same category.
    """
    rows = []
    for build in BUILDS:
        damage = math.fsum(e.log_gain for e in effects if build in e.builds and e.kind == "Damage")
        gold = math.fsum(e.log_gain for e in effects if build in e.builds and e.kind == "Gold")
        rows.append((build, damage, gold, damage + gold_weight * gold))
    return sorted(rows, key=lambda row: -row[3])


def compare_prestige_times(seconds_by_build):
    """Rank completed runs over the same stage range by median elapsed time."""
    return sorted(
        ((build, median(runs), len(runs)) for build, runs in seconds_by_build.items() if runs),
        key=lambda row: row[1],
    )
