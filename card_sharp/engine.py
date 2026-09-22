import random
from dataclasses import dataclass, field
from typing import Optional
from .rules import Rules


RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K"]
SUITS = ["♠", "♥", "♦", "♣"]


def card_value(rank: str) -> int:
    if rank == "A":
        return 11
    if rank in ("T", "J", "Q", "K"):
        return 10
    return int(rank)


@dataclass
class Card:
    rank: str
    suit: str

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"


class Shoe:
    """Multi-deck shoe with a cut card at `penetration`."""

    def __init__(self, decks: int, penetration: float, rng: Optional[random.Random] = None):
        self.decks = decks
        self.penetration = penetration
        self.rng = rng or random.Random()
        self.cards: list[Card] = []
        self.cut_index: int = 0
        self.needs_shuffle: bool = True
        self._build_and_shuffle()

    def _build_and_shuffle(self):
        deck: list[Card] = []
        for _ in range(self.decks):
            for r in RANKS:
                for s in SUITS:
                    deck.append(Card(r, s))
        self.rng.shuffle(deck)
        self.cards = deck
        self.cut_index = int(len(deck) * self.penetration)
        self.needs_shuffle = False

    def dealt_count(self) -> int:
        return (self.decks * 52) - len(self.cards)

    def draw(self) -> Card:
        if not self.cards:
            self._build_and_shuffle()
        c = self.cards.pop()
        if self.dealt_count() >= self.cut_index:
            self.needs_shuffle = True  # will shuffle before next round
        return c

    def reshuffle_if_needed(self):
        if self.needs_shuffle:
            self._build_and_shuffle()


@dataclass
class Hand:
    cards: list[Card] = field(default_factory=list)
    bet: int = 0
    doubled: bool = False
    surrendered: bool = False
    is_split_hand: bool = False
    from_split_aces: bool = False
    stood: bool = False
    busted: bool = False

    def add(self, c: Card):
        self.cards.append(c)

    def totals(self) -> tuple[int, bool]:
        """Return (best total, is_soft)."""
        total = sum(card_value(c.rank) for c in self.cards)
        aces = sum(1 for c in self.cards if c.rank == "A")
        soft = False
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        if aces > 0 and total <= 21:
            soft = True
        return total, soft

    def best(self) -> int:
        return self.totals()[0]

    def is_soft(self) -> bool:
        return self.totals()[1]

    def is_blackjack(self) -> bool:
        return len(self.cards) == 2 and self.best() == 21 and not self.is_split_hand

    def is_pair(self) -> bool:
        if len(self.cards) != 2:
            return False
        a, b = self.cards
        # For strategy, 10/J/Q/K all count as pair of 10s
        return card_value(a.rank) == card_value(b.rank)

    def pair_rank(self) -> Optional[str]:
        if not self.is_pair():
            return None
        r = self.cards[0].rank
        return "T" if r in ("T", "J", "Q", "K") else r

    def can_double(self, rules: Rules) -> bool:
        if len(self.cards) != 2 or self.doubled or self.from_split_aces:
            return False
        total = self.best()
        if rules.double_on == "any2":
            return True
        if rules.double_on == "9_10_11":
            return total in (9, 10, 11)
        if rules.double_on == "10_11":
            return total in (10, 11)
        return False

    def can_split(self, rules: Rules, current_hand_count: int) -> bool:
        if not self.is_pair():
            return False
        if current_hand_count >= rules.split_max_hands:
            return False
        # Splitting aces again only if resplit_aces
        if self.cards[0].rank == "A" and current_hand_count > 1 and not rules.resplit_aces:
            return False
        return True

    def can_surrender(self, rules: Rules) -> bool:
        return rules.surrender in ("late", "early") and len(self.cards) == 2 and not self.is_split_hand


@dataclass
class RoundResult:
    hand: Hand
    payout: int              # net chips won/lost for this hand (excludes original bet return conceptually)
    outcome: str             # "win", "lose", "push", "blackjack", "surrender"


class Game:
    def __init__(self, rules: Rules, starting_bankroll: int = 1000, rng: Optional[random.Random] = None):
        self.rules = rules
        self.bankroll = starting_bankroll
        self.rng = rng or random.Random()
        self.shoe = Shoe(rules.decks, rules.penetration, self.rng)
        self.player_hands: list[Hand] = []
        self.active_hand_index: int = 0
        self.dealer_hand: Hand = Hand()
        self.in_round: bool = False

    def new_shoe(self):
        self.shoe = Shoe(self.rules.decks, self.rules.penetration, self.rng)

    def start_round(self, bet: int):
        assert not self.in_round, "round already active"
        assert bet > 0 and bet <= self.bankroll
        self.shoe.reshuffle_if_needed()
        self.player_hands = [Hand(bet=bet)]
        self.active_hand_index = 0
        self.dealer_hand = Hand()
        # deal
        self.player_hands[0].add(self.shoe.draw())
        self.dealer_hand.add(self.shoe.draw())
        self.player_hands[0].add(self.shoe.draw())
        self.dealer_hand.add(self.shoe.draw())
        self.bankroll -= bet
        self.in_round = True

    def active_hand(self) -> Hand:
        return self.player_hands[self.active_hand_index]

    def dealer_upcard(self) -> Card:
        # UI convention: dealer.cards[0] is the hidden hole, cards[1] is the visible upcard.
        return self.dealer_hand.cards[1]

    # --- player actions ---
    def hit(self):
        h = self.active_hand()
        h.add(self.shoe.draw())
        if h.best() > 21:
            h.busted = True
            self._advance_hand()
        elif h.from_split_aces and not self.rules.hit_split_aces:
            h.stood = True
            self._advance_hand()

    def stand(self):
        self.active_hand().stood = True
        self._advance_hand()

    def double(self):
        h = self.active_hand()
        assert h.can_double(self.rules)
        assert self.bankroll >= h.bet
        self.bankroll -= h.bet
        h.bet *= 2
        h.doubled = True
        h.add(self.shoe.draw())
        if h.best() > 21:
            h.busted = True
        self._advance_hand()

    def split(self):
        h = self.active_hand()
        assert h.can_split(self.rules, len(self.player_hands))
        assert self.bankroll >= h.bet
        self.bankroll -= h.bet
        c1, c2 = h.cards
        new1 = Hand(cards=[c1], bet=h.bet, is_split_hand=True, from_split_aces=(c1.rank == "A"))
        new2 = Hand(cards=[c2], bet=h.bet, is_split_hand=True, from_split_aces=(c2.rank == "A"))
        # replace current with two
        self.player_hands.pop(self.active_hand_index)
        self.player_hands.insert(self.active_hand_index, new2)
        self.player_hands.insert(self.active_hand_index, new1)
        # deal one to first
        h1 = self.player_hands[self.active_hand_index]
        h1.add(self.shoe.draw())
        # If aces and can't hit, auto-stand this hand
        if h1.from_split_aces and not self.rules.hit_split_aces:
            h1.stood = True
            self._advance_hand()
            # advance also deals second hand's card lazily below via _prime_new_hand
        # If normal split hand becomes 21 with dealt card, it's just 21 (not natural)

    def surrender(self):
        h = self.active_hand()
        assert h.can_surrender(self.rules)
        h.surrendered = True
        self._advance_hand()

    def _prime_new_hand(self):
        """After moving to a fresh split hand with only one card, deal it a second card."""
        while self.active_hand_index < len(self.player_hands):
            h = self.active_hand()
            if len(h.cards) == 1:
                h.add(self.shoe.draw())
                if h.from_split_aces and not self.rules.hit_split_aces:
                    h.stood = True
                    self.active_hand_index += 1
                    continue
            break

    def _advance_hand(self):
        self.active_hand_index += 1
        self._prime_new_hand()

    def all_hands_done(self) -> bool:
        return self.active_hand_index >= len(self.player_hands)

    # --- dealer play ---
    def dealer_play(self):
        # Only play out dealer if any player hand is live
        live = any(not (h.busted or h.surrendered) for h in self.player_hands)
        if not live:
            return
        while True:
            total, soft = self.dealer_hand.totals()
            if total < 17:
                self.dealer_hand.add(self.shoe.draw())
                continue
            if total == 17 and soft and self.rules.dealer_hits_soft_17:
                self.dealer_hand.add(self.shoe.draw())
                continue
            break

    def settle(self) -> list[RoundResult]:
        results: list[RoundResult] = []
        dealer_total = self.dealer_hand.best()
        dealer_bj = self.dealer_hand.is_blackjack()
        for h in self.player_hands:
            if h.surrendered:
                # lose half the original bet, return half
                half = h.bet // 2
                self.bankroll += half
                results.append(RoundResult(h, -half, "surrender"))
                continue
            if h.busted:
                results.append(RoundResult(h, -h.bet, "lose"))
                continue
            if h.is_blackjack():
                if dealer_bj:
                    self.bankroll += h.bet
                    results.append(RoundResult(h, 0, "push"))
                else:
                    win = int(h.bet * self.rules.blackjack_payout)
                    self.bankroll += h.bet + win
                    results.append(RoundResult(h, win, "blackjack"))
                continue
            if dealer_bj:
                results.append(RoundResult(h, -h.bet, "lose"))
                continue
            p = h.best()
            if dealer_total > 21 or p > dealer_total:
                self.bankroll += h.bet * 2
                results.append(RoundResult(h, h.bet, "win"))
            elif p == dealer_total:
                self.bankroll += h.bet
                results.append(RoundResult(h, 0, "push"))
            else:
                results.append(RoundResult(h, -h.bet, "lose"))
        self.in_round = False
        return results
