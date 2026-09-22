"""Situation generators for the Trainer.

Each generator returns (Hand, dealer_upcard_Card, category, drill_name).
The Hand is always 2 cards so can_double / can_split / can_surrender behave
correctly against Rules.
"""
import random
from typing import Callable
from .engine import Card, Hand, RANKS, SUITS, card_value


UPCARDS_ALL = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "A"]  # T for 10-value
UPCARDS_NO_A = ["2", "3", "4", "5", "6", "7", "8", "9", "T"]


def _rand_suit(rng: random.Random) -> str:
    return rng.choice(SUITS)


def _card(rng: random.Random, rank: str) -> Card:
    return Card(rank, _rand_suit(rng))


def _two_card_hand(rng: random.Random, r1: str, r2: str) -> Hand:
    h = Hand()
    h.add(_card(rng, r1))
    h.add(_card(rng, r2))
    return h


def _upcard(rng: random.Random, pool=UPCARDS_ALL) -> Card:
    return _card(rng, rng.choice(pool))


# ---------- Hard totals ----------
def gen_hard(rng: random.Random) -> tuple[Hand, Card, str, str]:
    """A 2-card hard hand vs any upcard. Favors 12-16 (tough zone)."""
    # Choose target total, weighted toward tough hands
    weights = {5:1, 6:1, 7:1, 8:2, 9:3, 10:2, 11:2,
               12:5, 13:5, 14:5, 15:6, 16:6, 17:3, 18:2, 19:1, 20:1}
    totals = list(weights.keys())
    w = list(weights.values())
    total = rng.choices(totals, weights=w, k=1)[0]

    # Build a 2-card hard hand summing to `total`, no soft ace
    for _ in range(50):
        # pick first card 2..10 (not A)
        r1_rank = rng.choice(["2","3","4","5","6","7","8","9","T"])
        v1 = card_value(r1_rank)
        v2 = total - v1
        if v2 < 2 or v2 > 10:
            continue
        r2_candidates = [r for r in ["2","3","4","5","6","7","8","9","T","J","Q","K"] if card_value(r) == v2]
        if not r2_candidates:
            continue
        r2_rank = rng.choice(r2_candidates)
        # Skip exact pairs (those belong in Splits drill)
        if card_value(r1_rank) == card_value(r2_rank):
            continue
        h = _two_card_hand(rng, r1_rank, r2_rank)
        # Sanity: no soft (no aces so guaranteed)
        return (h, _upcard(rng), "hard", "hard")
    # Fallback: hardcoded 10+6 vs T
    return (_two_card_hand(rng, "T", "6"), _card(rng, "T"), "hard", "hard")


# ---------- Soft hands ----------
def gen_soft(rng: random.Random) -> tuple[Hand, Card, str, str]:
    """A,2 through A,9 vs any upcard."""
    other = rng.choice(["2","3","4","5","6","7","8","9"])
    h = _two_card_hand(rng, "A", other)
    return (h, _upcard(rng), "soft", "soft")


# ---------- Splits ----------
def gen_splits(rng: random.Random) -> tuple[Hand, Card, str, str]:
    """Any pair (2,2 through 10,10, A,A) vs any upcard."""
    # 10-value pair: mix of T/J/Q/K
    r = rng.choice(["2","3","4","5","6","7","8","9","T","A"])
    if r == "T":
        r1, r2 = rng.sample(["T","J","Q","K"], 2)
    else:
        r1 = r2 = r
    h = _two_card_hand(rng, r1, r2)
    return (h, _upcard(rng), "pair", "splits")


# ---------- Doubles (candidate situations) ----------
def gen_doubles(rng: random.Random) -> tuple[Hand, Card, str, str]:
    """Situations where doubling is *plausibly* correct — hard 8-11 and soft 13-19."""
    mode = rng.choice(["hard", "soft"])
    if mode == "hard":
        total = rng.choice([8, 9, 10, 11])
        # pick two non-ace cards summing to total, non-pair
        for _ in range(30):
            r1 = rng.choice(["2","3","4","5","6","7","8","9"])
            v1 = card_value(r1)
            v2 = total - v1
            if v2 < 2 or v2 > 9:
                continue
            if v1 == v2:  # avoid pairs
                continue
            r2 = rng.choice([r for r in ["2","3","4","5","6","7","8","9"] if card_value(r) == v2])
            h = _two_card_hand(rng, r1, r2)
            return (h, _upcard(rng), "hard", "doubles")
        # Fallback
        return (_two_card_hand(rng, "6", "5"), _upcard(rng), "hard", "doubles")
    else:
        other = rng.choice(["2","3","4","5","6","7","8"])   # A,2..A,8
        h = _two_card_hand(rng, "A", other)
        return (h, _upcard(rng), "soft", "doubles")


# ---------- Surrender ----------
def gen_surrender(rng: random.Random) -> tuple[Hand, Card, str, str]:
    """Hard 14-17 vs 8/9/10/A — the zone where surrender is at least a candidate."""
    total = rng.choice([14, 15, 16, 17])
    for _ in range(30):
        r1 = rng.choice(["2","3","4","5","6","7","8","9","T"])
        v1 = card_value(r1)
        v2 = total - v1
        if v2 < 2 or v2 > 10:
            continue
        r2_pool = [r for r in ["2","3","4","5","6","7","8","9","T","J","Q","K"] if card_value(r) == v2]
        if not r2_pool:
            continue
        r2 = rng.choice(r2_pool)
        if card_value(r1) == card_value(r2):
            continue  # pairs go to splits drill
        h = _two_card_hand(rng, r1, r2)
        up = _card(rng, rng.choice(["8","9","T","A"]))
        return (h, up, "hard", "surrender")
    return (_two_card_hand(rng, "T", "6"), _card(rng, "T"), "hard", "surrender")


# ---------- Mixed ----------
def gen_mixed(rng: random.Random) -> tuple[Hand, Card, str, str]:
    picks = [gen_hard, gen_soft, gen_splits, gen_doubles, gen_surrender]
    weights = [3, 2, 2, 2, 1]
    gen = rng.choices(picks, weights=weights, k=1)[0]
    h, up, cat, _ = gen(rng)
    return (h, up, cat, "mixed")


GENERATORS: dict[str, Callable] = {
    "hard": gen_hard,
    "soft": gen_soft,
    "splits": gen_splits,
    "doubles": gen_doubles,
    "surrender": gen_surrender,
    "mixed": gen_mixed,
}

DRILL_TITLES = {
    "hard": "Hard totals (2-cards, hard 5-20)",
    "soft": "Soft hands (A,2 – A,9)",
    "splits": "Splits (all pairs 2s–10s + A,A)",
    "doubles": "Doubles (hard 8-11 & soft 13-19)",
    "surrender": "Surrender (hard 14-17 vs 8/9/T/A)",
    "mixed": "Mixed — all categories",
}

DRILL_ORDER = ["hard", "soft", "splits", "doubles", "surrender", "mixed"]
