"""Personal strategy deviations (a.k.a. house/personal exceptions).

Storage: dict inside prefs.json under the key "deviations".
Key format:  "<hand_key>|<upcard>"
    hand_key: "hard_N" (5..20), "soft_N" (13..20), "pair_R" (R in 2..9, T, A)
    upcard:   "2","3","4","5","6","7","8","9","T","A"
Value: action code — one of "H","S","D","P","R"

Example:  {"hard_8|5": "D",  "hard_16|9": "R"}
"""
from typing import Optional
from .engine import Hand, card_value


UPCARD_KEYS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "A"]


def upcard_key(rank: str) -> str:
    if rank in ("J", "Q", "K"):
        return "T"
    return rank


def hand_key(hand: Hand) -> Optional[str]:
    """Compute the deviation key for a hand, or None if hand doesn't map cleanly."""
    if hand.is_pair():
        r = hand.cards[0].rank
        if r == "A":
            return "pair_A"
        v = card_value(r)  # T,J,Q,K all -> 10
        if v == 10:
            return "pair_T"
        return f"pair_{v}"
    total, soft = hand.totals()
    if soft and 13 <= total <= 20:
        return f"soft_{total}"
    if 5 <= total <= 20:
        return f"hard_{total}"
    return None


def get(deviations: dict, hand: Hand, up_rank: str) -> Optional[str]:
    hk = hand_key(hand)
    if not hk:
        return None
    key = f"{hk}|{upcard_key(up_rank)}"
    return deviations.get(key)


def set_(deviations: dict, hand_k: str, upcard: str, action: str) -> None:
    deviations[f"{hand_k}|{upcard_key(upcard)}"] = action


def remove(deviations: dict, hand_k: str, upcard: str) -> None:
    deviations.pop(f"{hand_k}|{upcard_key(upcard)}", None)


def list_all(deviations: dict) -> list[tuple[str, str, str]]:
    """Return sorted list of (hand_key, upcard, action)."""
    out = []
    for k, v in deviations.items():
        if "|" in k:
            hk, up = k.split("|", 1)
            out.append((hk, up, v))
    out.sort(key=lambda t: (_sort_hand(t[0]), _sort_up(t[1])))
    return out


def _sort_hand(hk: str) -> tuple[int, int]:
    # Order: hard 5..20, soft 13..20, pairs 2..10, pair A
    if hk.startswith("hard_"):
        return (0, int(hk.split("_")[1]))
    if hk.startswith("soft_"):
        return (1, int(hk.split("_")[1]))
    if hk == "pair_A":
        return (2, 99)
    if hk == "pair_T":
        return (2, 10)
    if hk.startswith("pair_"):
        return (2, int(hk.split("_")[1]))
    return (3, 0)


def _sort_up(up: str) -> int:
    if up == "A":
        return 11
    if up == "T":
        return 10
    return int(up)


def describe_hand_key(hk: str) -> str:
    if hk.startswith("hard_"):
        return f"Hard {hk.split('_')[1]}"
    if hk.startswith("soft_"):
        n = int(hk.split("_")[1])
        return f"Soft {n} (A,{n - 11})"
    if hk == "pair_A":
        return "Pair of Aces (A,A)"
    if hk == "pair_T":
        return "Pair of 10s (T,T)"
    if hk.startswith("pair_"):
        n = hk.split("_")[1]
        return f"Pair of {n}s ({n},{n})"
    return hk


# All valid hand keys for the editor UI dropdowns
HARD_KEYS = [f"hard_{n}" for n in range(5, 21)]
SOFT_KEYS = [f"soft_{n}" for n in range(13, 21)]     # A,2 .. A,9
PAIR_KEYS = [f"pair_{n}" for n in range(2, 10)] + ["pair_T", "pair_A"]

ACTION_OPTIONS = ["H", "S", "D", "P", "R"]
