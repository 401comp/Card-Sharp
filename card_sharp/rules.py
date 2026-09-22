from dataclasses import dataclass, asdict, field
from typing import Literal


SurrenderMode = Literal["none", "late", "early"]
DoubleMode = Literal["any2", "9_10_11", "10_11"]


@dataclass
class Rules:
    name: str
    decks: int = 6
    dealer_hits_soft_17: bool = False   # False = S17, True = H17
    blackjack_payout: float = 1.5        # 3:2 vs 6:5 (1.2)
    double_on: DoubleMode = "any2"
    double_after_split: bool = True
    split_max_hands: int = 4
    resplit_aces: bool = False
    hit_split_aces: bool = False
    surrender: SurrenderMode = "none"
    penetration: float = 0.75            # portion dealt before shuffle
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Rules":
        return cls(**d)


# Best-estimate presets. VERIFY at the casino — rules vary by pit/table/limit.
# The Rules panel lets the user correct these anytime.
PRESETS: dict[str, Rules] = {
    "Foxwoods — 6D Main Pit": Rules(
        name="Foxwoods — 6D Main Pit",
        decks=6, dealer_hits_soft_17=False, blackjack_payout=1.5,
        double_after_split=True, surrender="none",
        notes="Estimate: 6 decks, S17, DAS, no surrender, 3:2. Verify at table.",
    ),
    "Foxwoods — 8D Low Limit": Rules(
        name="Foxwoods — 8D Low Limit",
        decks=8, dealer_hits_soft_17=True, blackjack_payout=1.5,
        double_after_split=True, surrender="none",
        notes="Estimate: 8 decks, H17, DAS, 3:2. Low-limit tables sometimes 6:5 — check.",
    ),
    "Mohegan Sun — 6D": Rules(
        name="Mohegan Sun — 6D",
        decks=6, dealer_hits_soft_17=False, blackjack_payout=1.5,
        double_after_split=True, surrender="none",
        notes="Estimate: 6 decks, S17, DAS, no surrender, 3:2. Verify at table.",
    ),
    "Mohegan Sun — 8D": Rules(
        name="Mohegan Sun — 8D",
        decks=8, dealer_hits_soft_17=True, blackjack_payout=1.5,
        double_after_split=True, surrender="none",
        notes="Estimate: 8 decks, H17, DAS, 3:2.",
    ),
    "Bally Twin River — 6D": Rules(
        name="Bally Twin River — 6D",
        decks=6, dealer_hits_soft_17=True, blackjack_payout=1.5,
        double_after_split=True, surrender="late",
        notes="Estimate: 6 decks, H17, DAS, late surrender, 3:2. Verify.",
    ),
    "Bally Twin River — 8D": Rules(
        name="Bally Twin River — 8D",
        decks=8, dealer_hits_soft_17=True, blackjack_payout=1.5,
        double_after_split=True, surrender="late",
        notes="Estimate: 8 decks, H17, DAS, late surrender, 3:2.",
    ),
    # Atlantic City properties share state-mandated player protections, but
    # floor, limit, and shift can still change deck count and H17/S17. These
    # are practical starting points, not a claim that every open table matches.
    "Ocean Casino Resort — 6D S17": Rules(
        name="Ocean Casino Resort — 6D S17",
        decks=6, dealer_hits_soft_17=False, blackjack_payout=1.5,
        double_after_split=True, split_max_hands=3, surrender="late",
        notes="Best estimate: 6D, S17, DAS, late surrender, 3:2. Ocean publishes both S17/H17 and 6D/8D tables; verify the felt.",
    ),
    "Ocean Casino Resort — 8D H17": Rules(
        name="Ocean Casino Resort — 8D H17",
        decks=8, dealer_hits_soft_17=True, blackjack_payout=1.5,
        double_after_split=True, split_max_hands=3, surrender="late",
        notes="Best estimate: 8D, H17, DAS, late surrender, 3:2. Ocean publishes table-specific S17/H17 rules; verify the felt.",
    ),
    "Borgata — 8D Atlantic City": Rules(
        name="Borgata — 8D Atlantic City",
        decks=8, dealer_hits_soft_17=False, blackjack_payout=1.5,
        double_after_split=True, split_max_hands=3, surrender="late",
        notes="Atlantic City baseline: 8D, S17, DAS, late surrender, 3:2. Check the individual table and minimum.",
    ),
    "Harrah's Atlantic City — 8D": Rules(
        name="Harrah's Atlantic City — 8D",
        decks=8, dealer_hits_soft_17=False, blackjack_payout=1.5,
        double_after_split=True, split_max_hands=3, surrender="late",
        notes="Atlantic City baseline: 8D, S17, DAS, late surrender, 3:2. Check the individual table and minimum.",
    ),
    "Caesars Atlantic City — 8D": Rules(
        name="Caesars Atlantic City — 8D",
        decks=8, dealer_hits_soft_17=False, blackjack_payout=1.5,
        double_after_split=True, split_max_hands=3, surrender="late",
        notes="Atlantic City baseline: 8D, S17, DAS, late surrender, 3:2. Check the individual table and minimum.",
    ),
    "Tropicana Atlantic City — 8D H17": Rules(
        name="Tropicana Atlantic City — 8D H17",
        decks=8, dealer_hits_soft_17=True, blackjack_payout=1.5,
        double_after_split=True, split_max_hands=3, surrender="late",
        notes="Best estimate: 8D, H17, DAS, late surrender, 3:2. Table signage is authoritative.",
    ),
    "Hard Rock Atlantic City — 8D H17": Rules(
        name="Hard Rock Atlantic City — 8D H17",
        decks=8, dealer_hits_soft_17=True, blackjack_payout=1.5,
        double_after_split=True, split_max_hands=3, surrender="late",
        notes="Best estimate: 8D, H17, DAS, late surrender, 3:2. Table signage is authoritative.",
    ),
    "Golden Nugget Atlantic City — 6D S17": Rules(
        name="Golden Nugget Atlantic City — 6D S17",
        decks=6, dealer_hits_soft_17=False, blackjack_payout=1.5,
        double_after_split=True, split_max_hands=3, surrender="none",
        notes="Best estimate: 6D, S17, DAS, no surrender, 3:2. Check the individual table and minimum.",
    ),
    "MGM Springfield — 6D S17": Rules(
        name="MGM Springfield — 6D S17",
        decks=6, dealer_hits_soft_17=False, blackjack_payout=1.5,
        double_after_split=True, split_max_hands=4, resplit_aces=True, surrender="late",
        notes="Best estimate: 6D, S17, DAS, resplit aces, late surrender, 3:2. Massachusetts-approved rules and table conditions vary; verify at table.",
    ),
    "Custom (Vegas Strip 6D S17)": Rules(
        name="Custom (Vegas Strip 6D S17)",
        decks=6, dealer_hits_soft_17=False, blackjack_payout=1.5,
        double_after_split=True, surrender="none",
        notes="Baseline reference table.",
    ),
}


def default_preset_name() -> str:
    return "Foxwoods — 6D Main Pit"
