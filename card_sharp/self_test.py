"""Sanity self-tests: strategy answers, engine invariants, shoe behavior.

Run:  python -m card_sharp.self_test
"""
import random
from .engine import Card, Hand, Shoe, Game
from .rules import Rules, PRESETS
from .strategy import basic_strategy


FAIL = 0
PASS = 0


def check(label, cond):
    global FAIL, PASS
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label}")


def _hand(*cards) -> Hand:
    h = Hand()
    for r in cards:
        h.add(Card(r, "♠"))
    return h


def test_strategy_S17_DAS():
    print("Strategy — 6D S17 DAS (Foxwoods baseline)")
    r = PRESETS["Foxwoods — 6D Main Pit"]
    # Hard 16 vs 10 -> H (no surrender in this preset)
    check("hard 16 vs 10 -> H", basic_strategy(_hand("T", "6"), "T", r, 1) == "H")
    # Hard 12 vs 3 -> H
    check("hard 12 vs 3 -> H", basic_strategy(_hand("T", "2"), "3", r, 1) == "H")
    # Hard 12 vs 4 -> S
    check("hard 12 vs 4 -> S", basic_strategy(_hand("T", "2"), "4", r, 1) == "S")
    # Hard 11 vs A (S17) -> H
    check("hard 11 vs A (S17) -> H", basic_strategy(_hand("6", "5"), "A", r, 1) == "H")
    # Soft 18 vs 9 -> H
    check("soft 18 vs 9 -> H", basic_strategy(_hand("A", "7"), "9", r, 1) == "H")
    # Soft 18 vs 3 -> D (can double 2 cards)
    check("soft 18 vs 3 -> D", basic_strategy(_hand("A", "7"), "3", r, 1) == "D")
    # 8,8 vs A -> P (no surrender)
    check("8,8 vs A -> P", basic_strategy(_hand("8", "8"), "A", r, 1) == "P")
    # A,A always split
    check("A,A vs 5 -> P", basic_strategy(_hand("A", "A"), "5", r, 1) == "P")
    # T,T never split
    check("T,T vs 6 -> S", basic_strategy(_hand("T", "T"), "6", r, 1) == "S")


def test_strategy_H17_late_surrender():
    print("Strategy — 6D H17 late surrender (Bally Twin River)")
    r = PRESETS["Bally Twin River — 6D"]
    # 16 vs 9 -> R
    check("16 vs 9 -> R", basic_strategy(_hand("T", "6"), "9", r, 1) == "R")
    # 16 vs 10 -> R
    check("16 vs 10 -> R", basic_strategy(_hand("T", "6"), "T", r, 1) == "R")
    # 15 vs 10 -> R
    check("15 vs 10 -> R", basic_strategy(_hand("9", "6"), "T", r, 1) == "R")
    # 11 vs A -> D (H17)
    check("11 vs A H17 -> D", basic_strategy(_hand("6", "5"), "A", r, 1) == "D")
    # Soft 18 vs 2 -> D (Ds, has 2 cards -> D)
    check("soft 18 vs 2 H17 -> D", basic_strategy(_hand("A", "7"), "2", r, 1) == "D")


def test_hand_totals():
    print("Hand totals")
    h = _hand("A", "6")
    t, soft = h.totals()
    check("A,6 soft 17", t == 17 and soft)
    h.add(Card("T", "♣"))
    t, soft = h.totals()
    check("A,6,T hard 17", t == 17 and not soft)
    h2 = _hand("K", "K")
    check("K,K total 20", h2.best() == 20 and h2.is_pair())


def test_shoe_reshuffle():
    print("Shoe reshuffle")
    s = Shoe(decks=1, penetration=0.5, rng=random.Random(42))
    # Draw past cut
    dealt = 0
    while not s.needs_shuffle:
        s.draw()
        dealt += 1
    check("cut card triggers reshuffle", s.needs_shuffle)
    s.reshuffle_if_needed()
    check("reshuffle clears flag", not s.needs_shuffle)


def test_game_round():
    print("Game round smoke test")
    r = PRESETS["Foxwoods — 6D Main Pit"]
    g = Game(r, starting_bankroll=1000, rng=random.Random(1))
    g.start_round(25)
    check("bet debited", g.bankroll == 975)
    check("2 cards each dealt", len(g.player_hands[0].cards) == 2 and len(g.dealer_hand.cards) == 2)
    # Just stand and settle
    g.stand()
    g.dealer_play()
    results = g.settle()
    check("one result", len(results) == 1)
    check("round ended", not g.in_round)


def test_bj_payout():
    print("Blackjack payout")
    r = PRESETS["Foxwoods — 6D Main Pit"]
    g = Game(r, starting_bankroll=1000, rng=random.Random(1))
    # Manually stage a player BJ vs dealer non-BJ
    g.in_round = True
    g.bankroll -= 100
    h = Hand(bet=100)
    h.cards = [Card("A", "♠"), Card("K", "♥")]
    g.player_hands = [h]
    g.active_hand_index = 1  # all done
    g.dealer_hand = Hand()
    g.dealer_hand.cards = [Card("9", "♠"), Card("8", "♥")]  # 17
    results = g.settle()
    check("player BJ wins 3:2", results[0].payout == 150 and g.bankroll == 1000 + 150)


def test_multi_seat_smoke():
    print("Multi-seat table: round smoke test")
    from .table_game import Table, Seat, npc_action
    rng = random.Random(3)
    r = PRESETS["Foxwoods — 6D Main Pit"]
    seats = [
        Seat("Alice", "basic"),
        Seat("You",   "you"),
        Seat("Moron", "moron"),
        Seat("Wild",  "random"),
    ]
    t = Table(r, seats, rng)
    t.start_round([25, 25, 25, 25])
    check("dealer got 2 cards", len(t.dealer_hand.cards) == 2)
    for s in t.seats:
        check(f"{s.name} got 2 cards", len(s.hands[0].cards) == 2)
    # Play out: 'you' seat auto-stands, NPCs choose
    max_steps = 60
    while not t.all_players_done() and max_steps > 0:
        seat = t.current_seat()
        if seat is None:
            break
        if seat.is_you:
            t.apply_action("S")
        else:
            act = npc_action(seat, t.dealer_upcard().rank, r, rng)
            legal, _ = t.apply_action(act)
            if not legal:
                t.apply_action("S")
        max_steps -= 1
    check("all players done", t.all_players_done())
    t.dealer_play()
    results = t.settle()
    check("results per seat", len(results) == len(seats))


def test_overrides_and_resolve():
    print("Overrides + resolve_action")
    from . import overrides
    from .strategy import resolve_action, basic_strategy
    r = PRESETS["Foxwoods — 6D Main Pit"]
    # Baseline: hard 8 vs 5 = H per BS
    h = _hand("3", "5")
    check("BS: hard 8 vs 5 = H", basic_strategy(h, "5", r, 1) == "H")
    devs = {}
    overrides.set_(devs, "hard_8", "5", "D")
    accepted, bs, is_dev = resolve_action(h, "5", r, 1, devs)
    check("resolve returns D as accepted", accepted == "D")
    check("resolve returns H as bs", bs == "H")
    check("is_deviation flag set", is_dev is True)
    # If the deviation is illegal (already 3 cards can't double), fall back to BS
    h3 = _hand("3", "5")
    h3.add(Card("2", "♠"))     # now 3 cards, can't double
    accepted2, bs2, is_dev2 = resolve_action(h3, "5", r, 1, devs)
    check("illegal deviation -> falls back to BS", accepted2 == bs2 and not is_dev2)
    # No deviation set: is_dev False
    accepted3, bs3, is_dev3 = resolve_action(_hand("T", "6"), "T", r, 1, {})
    check("empty deviations: no deviation flag", not is_dev3 and accepted3 == bs3)


def test_drill_generators():
    print("Drill generators")
    from .drills import GENERATORS
    rng = random.Random(1)
    for name, gen in GENERATORS.items():
        for _ in range(50):
            h, up, cat, drill = gen(rng)
            check(f"{name}: 2-card hand", len(h.cards) == 2)
            check(f"{name}: upcard rank in valid set", up.rank in ["A","2","3","4","5","6","7","8","9","T","J","Q","K"])
            check(f"{name}: category in {{hard, soft, pair}}", cat in ("hard", "soft", "pair"))


def test_dealer_upcard_helper():
    print("Dealer upcard helper (regression: strategy vs visible card)")
    r = PRESETS["Foxwoods — 6D Main Pit"]
    g = Game(r, starting_bankroll=1000, rng=random.Random(7))
    g.start_round(25)
    up = g.dealer_upcard()
    check("upcard is cards[1]", up is g.dealer_hand.cards[1])


def main():
    test_strategy_S17_DAS()
    test_strategy_H17_late_surrender()
    test_hand_totals()
    test_shoe_reshuffle()
    test_game_round()
    test_bj_payout()
    test_dealer_upcard_helper()
    test_drill_generators()
    test_overrides_and_resolve()
    test_multi_seat_smoke()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
