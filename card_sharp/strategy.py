"""Basic strategy for multi-deck shoe games (6D/8D). Adjusts for H17 and surrender.

Returns one of: "H" hit, "S" stand, "D" double, "P" split, "R" surrender.
The chart uses richer tokens internally, then downgrades to a legal action.
"""
from .engine import Hand, card_value
from .rules import Rules


# Upcard index: 2..10, 11 = Ace
def upcard_index(rank: str) -> int:
    if rank == "A":
        return 11
    if rank in ("T", "J", "Q", "K"):
        return 10
    return int(rank)


# --- Chart tokens ---
# H, S, D, P, R (surrender)
# Ds = double if allowed else stand
# Ph = split if DAS else hit
# Rh = surrender if allowed else hit
# Rs = surrender if allowed else stand
# Rp = surrender if allowed else split (used for 8,8 vs A in some H17 charts)

# Index by upcard 2..11
def _row(m: dict[int, str]) -> dict[int, str]:
    return m


# Hard totals 5..21
HARD_S17 = {
    5:  {u: "H" for u in range(2, 12)},
    6:  {u: "H" for u in range(2, 12)},
    7:  {u: "H" for u in range(2, 12)},
    8:  {u: "H" for u in range(2, 12)},
    9:  {2:"H", 3:"D", 4:"D", 5:"D", 6:"D", 7:"H", 8:"H", 9:"H", 10:"H", 11:"H"},
    10: {2:"D", 3:"D", 4:"D", 5:"D", 6:"D", 7:"D", 8:"D", 9:"D", 10:"H", 11:"H"},
    11: {2:"D", 3:"D", 4:"D", 5:"D", 6:"D", 7:"D", 8:"D", 9:"D", 10:"D", 11:"H"},
    12: {2:"H", 3:"H", 4:"S", 5:"S", 6:"S", 7:"H", 8:"H", 9:"H", 10:"H", 11:"H"},
    13: {2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"H", 8:"H", 9:"H", 10:"H", 11:"H"},
    14: {2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"H", 8:"H", 9:"H", 10:"H", 11:"H"},
    15: {2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"H", 8:"H", 9:"H", 10:"Rh", 11:"H"},
    16: {2:"S", 3:"S", 4:"S", 5:"S", 6:"S", 7:"H", 8:"H", 9:"Rh", 10:"Rh", 11:"Rh"},
    17: {u: "S" for u in range(2, 12)},
    18: {u: "S" for u in range(2, 12)},
    19: {u: "S" for u in range(2, 12)},
    20: {u: "S" for u in range(2, 12)},
    21: {u: "S" for u in range(2, 12)},
}

# H17 differences from S17
HARD_H17_OVERRIDES = {
    11: {11: "D"},          # 11 vs A: double
    15: {11: "Rh"},         # surrender 15 vs A (late)
    17: {11: "Rs"},         # surrender 17 vs A (late)  — some charts include
}

# Soft totals — key = non-ace card value with the ace (so A,2 = 13; A,7 = 18; A,9 = 20)
SOFT_S17 = {
    13: {2:"H", 3:"H", 4:"H", 5:"D", 6:"D", 7:"H", 8:"H", 9:"H", 10:"H", 11:"H"},
    14: {2:"H", 3:"H", 4:"H", 5:"D", 6:"D", 7:"H", 8:"H", 9:"H", 10:"H", 11:"H"},
    15: {2:"H", 3:"H", 4:"D", 5:"D", 6:"D", 7:"H", 8:"H", 9:"H", 10:"H", 11:"H"},
    16: {2:"H", 3:"H", 4:"D", 5:"D", 6:"D", 7:"H", 8:"H", 9:"H", 10:"H", 11:"H"},
    17: {2:"H", 3:"D", 4:"D", 5:"D", 6:"D", 7:"H", 8:"H", 9:"H", 10:"H", 11:"H"},
    18: {2:"S", 3:"Ds", 4:"Ds", 5:"Ds", 6:"Ds", 7:"S", 8:"S", 9:"H", 10:"H", 11:"H"},
    19: {u: "S" for u in range(2, 12)},
    20: {u: "S" for u in range(2, 12)},
    21: {u: "S" for u in range(2, 12)},
}

SOFT_H17_OVERRIDES = {
    18: {2: "Ds", 11: "H"},   # A,7 vs 2 becomes Ds; vs A stays H (some charts Rh — omitted for simplicity)
    19: {6: "Ds"},            # A,8 vs 6 becomes Ds
}

# Pairs — assume DAS available; adjust in code if not.
# Key = pair rank as int (11 = aces, 10 = ten-value)
PAIRS_S17 = {
    2:  {2:"P",  3:"P",  4:"P", 5:"P", 6:"P", 7:"P", 8:"H", 9:"H", 10:"H", 11:"H"},
    3:  {2:"P",  3:"P",  4:"P", 5:"P", 6:"P", 7:"P", 8:"H", 9:"H", 10:"H", 11:"H"},
    4:  {2:"H",  3:"H",  4:"H", 5:"P", 6:"P", 7:"H", 8:"H", 9:"H", 10:"H", 11:"H"},
    5:  {u: "D" if u <= 9 else "H" for u in range(2, 12)},  # never split — treat as hard 10
    6:  {2:"P",  3:"P",  4:"P", 5:"P", 6:"P", 7:"H", 8:"H", 9:"H", 10:"H", 11:"H"},
    7:  {2:"P",  3:"P",  4:"P", 5:"P", 6:"P", 7:"P", 8:"H", 9:"H", 10:"H", 11:"H"},
    8:  {2:"P",  3:"P",  4:"P", 5:"P", 6:"P", 7:"P", 8:"P", 9:"P", 10:"P", 11:"P"},
    9:  {2:"P",  3:"P",  4:"P", 5:"P", 6:"P", 7:"S", 8:"P", 9:"P", 10:"S", 11:"S"},
    10: {u: "S" for u in range(2, 12)},
    11: {u: "P" for u in range(2, 12)},
}

# Non-DAS overrides for pairs (some hands split only if DAS available)
PAIRS_NO_DAS = {
    2:  {2: "H", 3: "H"},
    3:  {2: "H", 3: "H"},
    4:  {5: "H", 6: "H"},
    6:  {2: "H"},
    7:  {8: "H"},  # 7,7 vs 8 without DAS — rarely applicable but harmless
}

PAIRS_H17_OVERRIDES = {
    8: {11: "Rp"},   # 8,8 vs A in H17 late surrender: some charts surrender; we downgrade to P if not allowed
}


def _apply_overrides(base: dict, overrides: dict) -> dict:
    out = {k: dict(v) for k, v in base.items()}
    for k, row in overrides.items():
        out.setdefault(k, {}).update(row)
    return out


def _resolve_token(token: str, hand: Hand, rules: Rules, current_hand_count: int) -> str:
    """Translate chart token to a legal action given hand context + rules."""
    if token == "H":
        return "H"
    if token == "S":
        return "S"
    if token == "D":
        return "D" if hand.can_double(rules) else "H"
    if token == "Ds":
        return "D" if hand.can_double(rules) else "S"
    if token == "P":
        return "P" if hand.can_split(rules, current_hand_count) else "H"
    if token == "Ph":
        # split if DAS; the base already assumes DAS, so this shouldn't fire here — safety
        if rules.double_after_split and hand.can_split(rules, current_hand_count):
            return "P"
        return "H"
    if token == "R":
        return "R" if hand.can_surrender(rules) else "H"
    if token == "Rh":
        return "R" if hand.can_surrender(rules) else "H"
    if token == "Rs":
        return "R" if hand.can_surrender(rules) else "S"
    if token == "Rp":
        return "R" if hand.can_surrender(rules) else ("P" if hand.can_split(rules, current_hand_count) else "H")
    return "S"


def basic_strategy(hand: Hand, dealer_upcard_rank: str, rules: Rules, current_hand_count: int) -> str:
    """Return the recommended action code for this situation."""
    up = upcard_index(dealer_upcard_rank)

    # Pairs first (only on initial 2 cards)
    if hand.is_pair() and hand.can_split(rules, current_hand_count):
        pair_val = card_value(hand.cards[0].rank)
        table = _apply_overrides(PAIRS_S17, PAIRS_H17_OVERRIDES if rules.dealer_hits_soft_17 else {})
        if not rules.double_after_split:
            table = _apply_overrides(table, PAIRS_NO_DAS)
        row = table.get(pair_val, {})
        token = row.get(up, "H")
        return _resolve_token(token, hand, rules, current_hand_count)

    total, soft = hand.totals()

    # Soft totals (must have an ace still counted as 11)
    if soft and 13 <= total <= 21:
        table = _apply_overrides(SOFT_S17, SOFT_H17_OVERRIDES if rules.dealer_hits_soft_17 else {})
        row = table.get(total, {u: "S" for u in range(2, 12)})
        token = row.get(up, "S")
        return _resolve_token(token, hand, rules, current_hand_count)

    # Hard totals
    table = _apply_overrides(HARD_S17, HARD_H17_OVERRIDES if rules.dealer_hits_soft_17 else {})
    total_clamped = max(5, min(21, total))
    row = table.get(total_clamped, {u: "H" for u in range(2, 12)})
    token = row.get(up, "H")
    return _resolve_token(token, hand, rules, current_hand_count)


ACTION_NAMES = {
    "H": "Hit",
    "S": "Stand",
    "D": "Double",
    "P": "Split",
    "R": "Surrender",
}


def _is_action_legal(action: str, hand: Hand, rules: Rules, current_hand_count: int) -> bool:
    if action in ("H", "S"):
        return True
    if action == "D":
        return hand.can_double(rules)
    if action == "P":
        return hand.can_split(rules, current_hand_count)
    if action == "R":
        return hand.can_surrender(rules)
    return False


def resolve_action(
    hand: Hand,
    dealer_upcard_rank: str,
    rules: Rules,
    current_hand_count: int,
    deviations: dict | None = None,
) -> tuple[str, str, bool]:
    """Return (accepted_action, basic_strategy_action, is_deviation).

    If the user has a personal deviation for (hand, upcard) AND that action is
    legal in the current situation, it becomes the accepted answer.
    Basic-strategy answer is always returned so the UI can show the book play.
    """
    bs = basic_strategy(hand, dealer_upcard_rank, rules, current_hand_count)
    if deviations:
        # Local import to avoid a cycle: overrides imports from engine only.
        from . import overrides as _ov
        dev = _ov.get(deviations, hand, dealer_upcard_rank)
        if dev and dev != bs and _is_action_legal(dev, hand, rules, current_hand_count):
            return (dev, bs, True)
    return (bs, bs, False)
