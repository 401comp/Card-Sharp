"""Multi-seat table game. Runs 2-6 seats around a single shoe.

Each seat has a personality that decides its action on each turn.
The user occupies exactly one seat (personality = 'you'); the UI feeds
that seat's action externally instead of consulting the strategy fn.
"""
import random
from dataclasses import dataclass, field
from typing import Optional

from .engine import Card, Hand, Shoe
from .rules import Rules
from .strategy import basic_strategy


PERSONALITIES = ["basic", "tight", "aggressive", "random", "wreck", "moron", "you"]

PERSONALITY_DESC = {
    "basic":      "Plays perfect basic strategy",
    "tight":      "Never doubles/splits/surrenders; hits to 17 (soft 18)",
    "aggressive": "Splits every pair, doubles 9/10/11, hits to 20",
    "random":     "Picks a random legal action",
    "wreck":      "40% chance of doing the opposite of basic strategy",
    "moron":      "Splits 10s, hits stiffs vs dealer weak card, never doubles",
    "you":        "You control this seat",
}


@dataclass
class Seat:
    name: str
    personality: str
    bankroll: int = 500
    bet: int = 25
    hands: list[Hand] = field(default_factory=list)
    active_hand_index: int = 0
    done: bool = False

    @property
    def is_you(self) -> bool:
        return self.personality == "you"

    def active_hand(self) -> Optional[Hand]:
        if not self.hands or self.active_hand_index >= len(self.hands):
            return None
        return self.hands[self.active_hand_index]


def npc_action(seat: Seat, upcard_rank: str, rules: Rules, rng: random.Random) -> str:
    """Return H/S/D/P/R for the seat's active hand. Assumes not 'you'."""
    hand = seat.active_hand()
    assert hand is not None
    hand_count = len(seat.hands)
    p = seat.personality

    if p == "basic":
        return basic_strategy(hand, upcard_rank, rules, hand_count)

    total, soft = hand.totals()

    if p == "tight":
        # never double, split, or surrender
        if soft:
            return "S" if total >= 18 else "H"
        return "S" if total >= 17 else "H"

    if p == "aggressive":
        if hand.is_pair() and hand.can_split(rules, hand_count) and seat.bankroll >= hand.bet:
            return "P"
        if hand.can_double(rules) and total in (9, 10, 11) and seat.bankroll >= hand.bet:
            return "D"
        return "S" if total >= 20 else "H"

    if p == "random":
        opts = ["H", "S"]
        if hand.can_double(rules) and seat.bankroll >= hand.bet:
            opts.append("D")
        if hand.can_split(rules, hand_count) and seat.bankroll >= hand.bet:
            opts.append("P")
        if hand.can_surrender(rules):
            opts.append("R")
        return rng.choice(opts)

    if p == "wreck":
        correct = basic_strategy(hand, upcard_rank, rules, hand_count)
        if rng.random() < 0.40:
            flip = {"H": "S", "S": "H", "D": "H", "P": "H", "R": "H"}
            alt = flip.get(correct, correct)
            # Only use the flipped action if legal; else fall back to correct.
            if alt in ("H", "S"):
                return alt
            return alt
        return correct

    if p == "moron":
        # 1. Splits tens if allowed
        if hand.is_pair() and hand.cards[0].rank in ("T", "J", "Q", "K"):
            if hand.can_split(rules, hand_count) and seat.bankroll >= hand.bet:
                return "P"
        # 2. Hits stiffs (hard 12-16) vs dealer weak upcard (2-6) — the classic table crime
        try:
            up_val = 11 if upcard_rank == "A" else (10 if upcard_rank in ("T","J","Q","K") else int(upcard_rank))
        except Exception:
            up_val = 10
        if not soft and 12 <= total <= 16 and 2 <= up_val <= 6:
            return "H"
        # 3. Never doubles, never surrenders
        # 4. Stands on soft 17
        if soft and total == 17:
            return "S"
        # Otherwise a rough basic-strategy approximation without D/R
        base = basic_strategy(hand, upcard_rank, rules, hand_count)
        if base in ("D",):
            # Would double -> just hit
            return "H"
        if base == "R":
            return "H"
        return base

    # unknown personality -> basic
    return basic_strategy(hand, upcard_rank, rules, hand_count)


class Table:
    def __init__(self, rules: Rules, seats: list[Seat], rng: Optional[random.Random] = None):
        assert 1 <= len(seats) <= 6
        self.rules = rules
        self.seats = seats
        self.rng = rng or random.Random()
        self.shoe = Shoe(rules.decks, rules.penetration, self.rng)
        self.dealer_hand = Hand()
        self.current_seat_index = 0
        self.in_round = False

    def new_shoe(self):
        self.shoe = Shoe(self.rules.decks, self.rules.penetration, self.rng)

    # ---- round setup / dealing ----
    def start_round(self, bets: list[int]):
        assert not self.in_round
        assert len(bets) == len(self.seats)
        self.shoe.reshuffle_if_needed()
        # Reset seats
        for s, b in zip(self.seats, bets):
            b = min(b, s.bankroll) if s.bankroll > 0 else 0
            s.hands = [Hand(bet=b)] if b > 0 else []
            s.active_hand_index = 0
            s.done = (b == 0)
            if b > 0:
                s.bankroll -= b
        self.dealer_hand = Hand()

        # Deal in casino-ish order. UI hides dealer.cards[0]; visible = cards[1].
        # So we deal HOLE first, then loop players first card, then UPCARD, then players second card.
        # That preserves the existing "hide index 0, show index 1" convention.
        self.dealer_hand.add(self.shoe.draw())   # cards[0] hidden
        for s in self.seats:
            if s.hands:
                s.hands[0].add(self.shoe.draw())
        self.dealer_hand.add(self.shoe.draw())   # cards[1] visible upcard
        for s in self.seats:
            if s.hands:
                s.hands[0].add(self.shoe.draw())

        self.current_seat_index = 0
        self._advance_to_next_actor()
        self.in_round = True

    def dealer_upcard(self) -> Card:
        return self.dealer_hand.cards[1]

    # ---- turn management ----
    def current_seat(self) -> Optional[Seat]:
        if 0 <= self.current_seat_index < len(self.seats):
            return self.seats[self.current_seat_index]
        return None

    def _advance_to_next_actor(self):
        """Skip seats that have no live hands or are done."""
        while self.current_seat_index < len(self.seats):
            s = self.seats[self.current_seat_index]
            if s.done or not s.hands:
                self.current_seat_index += 1
                continue
            # Check for blackjack on all hands => auto-done
            if all(h.is_blackjack() for h in s.hands):
                s.done = True
                self.current_seat_index += 1
                continue
            # find next non-finished hand in this seat
            while s.active_hand_index < len(s.hands):
                h = s.hands[s.active_hand_index]
                if h.busted or h.stood or h.surrendered:
                    s.active_hand_index += 1
                    continue
                if len(h.cards) == 1:
                    h.add(self.shoe.draw())
                    if h.from_split_aces and not self.rules.hit_split_aces:
                        h.stood = True
                        s.active_hand_index += 1
                        continue
                if h.is_blackjack():
                    s.active_hand_index += 1
                    continue
                return   # this seat has a live hand to act on
            # No live hand left in this seat
            s.done = True
            self.current_seat_index += 1

    def all_players_done(self) -> bool:
        return self.current_seat_index >= len(self.seats)

    # ---- actions (used by both player + NPCs) ----
    def apply_action(self, action: str) -> tuple[bool, str | None]:
        """Apply an action to the current seat's active hand.

        Returns (legal, drawn_card_str_or_None). drawn_card_str is set for
        H/D/P and is the card revealed by that action, so the UI can log it.
        """
        seat = self.current_seat()
        if seat is None:
            return (False, None)
        hand = seat.active_hand()
        if hand is None:
            return (False, None)

        drawn = None

        if action == "H":
            c = self.shoe.draw()
            hand.add(c)
            drawn = str(c)
            if hand.best() > 21:
                hand.busted = True
            if hand.busted or hand.best() == 21:
                seat.active_hand_index += 1
        elif action == "S":
            hand.stood = True
            seat.active_hand_index += 1
        elif action == "D":
            if not hand.can_double(self.rules) or seat.bankroll < hand.bet:
                return (False, None)
            seat.bankroll -= hand.bet
            hand.bet *= 2
            hand.doubled = True
            c = self.shoe.draw()
            hand.add(c)
            drawn = str(c)
            if hand.best() > 21:
                hand.busted = True
            seat.active_hand_index += 1
        elif action == "P":
            if not hand.can_split(self.rules, len(seat.hands)) or seat.bankroll < hand.bet:
                return (False, None)
            seat.bankroll -= hand.bet
            c1, c2 = hand.cards
            new1 = Hand(cards=[c1], bet=hand.bet, is_split_hand=True, from_split_aces=(c1.rank == "A"))
            new2 = Hand(cards=[c2], bet=hand.bet, is_split_hand=True, from_split_aces=(c2.rank == "A"))
            seat.hands.pop(seat.active_hand_index)
            seat.hands.insert(seat.active_hand_index, new2)
            seat.hands.insert(seat.active_hand_index, new1)
            # First split hand: deal its second card
            first = seat.hands[seat.active_hand_index]
            c = self.shoe.draw()
            first.add(c)
            drawn = str(c)
            if first.from_split_aces and not self.rules.hit_split_aces:
                first.stood = True
                seat.active_hand_index += 1
        elif action == "R":
            if not hand.can_surrender(self.rules):
                return (False, None)
            hand.surrendered = True
            seat.active_hand_index += 1
        else:
            return (False, None)

        # If this seat's hands are done, advance to next seat
        if seat.active_hand_index >= len(seat.hands):
            seat.done = True
            self.current_seat_index += 1
            self._advance_to_next_actor()
        else:
            # Prime new split hand if needed
            self._advance_to_next_actor_inside_seat(seat)
        return (True, drawn)

    def _advance_to_next_actor_inside_seat(self, seat: Seat):
        # If current hand only has 1 card (split just done), give it a card
        h = seat.active_hand()
        if h and len(h.cards) == 1:
            h.add(self.shoe.draw())
            if h.from_split_aces and not self.rules.hit_split_aces:
                h.stood = True
                seat.active_hand_index += 1
                if seat.active_hand_index >= len(seat.hands):
                    seat.done = True
                    self.current_seat_index += 1
                    self._advance_to_next_actor()

    # ---- dealer + settlement ----
    def dealer_play(self):
        live = any(
            any(not (h.busted or h.surrendered) for h in s.hands)
            for s in self.seats if s.hands
        )
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

    def settle(self) -> list[list[tuple[Hand, int, str]]]:
        """Return per-seat list of (hand, payout, outcome)."""
        results: list[list[tuple[Hand, int, str]]] = []
        dealer_total = self.dealer_hand.best()
        dealer_bj = self.dealer_hand.is_blackjack()
        for s in self.seats:
            seat_res: list[tuple[Hand, int, str]] = []
            for h in s.hands:
                if h.surrendered:
                    half = h.bet // 2
                    s.bankroll += half
                    seat_res.append((h, -half, "surrender"))
                    continue
                if h.busted:
                    seat_res.append((h, -h.bet, "lose"))
                    continue
                if h.is_blackjack():
                    if dealer_bj:
                        s.bankroll += h.bet
                        seat_res.append((h, 0, "push"))
                    else:
                        win = int(h.bet * self.rules.blackjack_payout)
                        s.bankroll += h.bet + win
                        seat_res.append((h, win, "blackjack"))
                    continue
                if dealer_bj:
                    seat_res.append((h, -h.bet, "lose"))
                    continue
                p = h.best()
                if dealer_total > 21 or p > dealer_total:
                    s.bankroll += h.bet * 2
                    seat_res.append((h, h.bet, "win"))
                elif p == dealer_total:
                    s.bankroll += h.bet
                    seat_res.append((h, 0, "push"))
                else:
                    seat_res.append((h, -h.bet, "lose"))
            results.append(seat_res)
        self.in_round = False
        return results
