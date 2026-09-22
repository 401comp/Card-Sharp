import random
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass

from .engine import Hand, Card
from .rules import Rules
from .strategy import basic_strategy, resolve_action, ACTION_NAMES
from .drills import GENERATORS, DRILL_TITLES, DRILL_ORDER
from . import db
from . import sounds


FELT = "#0b6b3a"
FELT_DARK = "#083f22"
CARD_BG = "#f7f2e7"
CARD_FG = "#111111"
CARD_RED = "#c02020"
TEXT_LIGHT = "#f2f2f2"
BTN_TEXT = "#111111"
GOOD = "#4caf50"
BAD = "#e53935"
WARN = "#ffb74d"


def center(win, w, h):
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//3}")


@dataclass
class TabState:
    attempts: int = 0
    correct: int = 0
    streak: int = 0
    best_streak: int = 0


class DrillTab(tk.Frame):
    """One drill tab — prompt card, action buttons, feedback, live stats."""

    def __init__(self, parent, drill_name: str, rules_getter, deviations_getter, rng: random.Random):
        super().__init__(parent, bg=FELT_DARK)
        self.drill_name = drill_name
        self.rules_getter = rules_getter
        self.deviations_getter = deviations_getter
        self.rng = rng
        self.state = TabState()
        self.current: tuple[Hand, Card, str] | None = None    # (hand, upcard, category)
        self.answered = False

        # Title / hint
        tk.Label(self, text=DRILL_TITLES[drill_name],
                 bg=FELT_DARK, fg=WARN,
                 font=("Helvetica", 14, "bold")).pack(pady=(10, 6))

        # Table view
        table = tk.Frame(self, bg=FELT, relief="ridge", bd=2)
        table.pack(fill="both", expand=True, padx=12, pady=6)

        # Dealer upcard (single card)
        dealer_row = tk.Frame(table, bg=FELT)
        dealer_row.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(dealer_row, text="Dealer shows:",
                 bg=FELT, fg=TEXT_LIGHT,
                 font=("Helvetica", 13, "bold")).pack(side="left")
        self.dealer_card_frame = tk.Frame(dealer_row, bg=FELT)
        self.dealer_card_frame.pack(side="left", padx=12)

        # Player hand
        player_row = tk.Frame(table, bg=FELT)
        player_row.pack(fill="x", padx=8, pady=(4, 8))
        tk.Label(player_row, text="Your hand:",
                 bg=FELT, fg=TEXT_LIGHT,
                 font=("Helvetica", 13, "bold")).pack(side="left")
        self.player_cards_frame = tk.Frame(player_row, bg=FELT)
        self.player_cards_frame.pack(side="left", padx=12)
        self.player_total_lbl = tk.Label(player_row, text="", bg=FELT, fg=TEXT_LIGHT,
                                         font=("Helvetica", 12))
        self.player_total_lbl.pack(side="left", padx=8)

        # Feedback area
        self.feedback_lbl = tk.Label(table, text="Pick the best action.",
                                     bg=FELT, fg=TEXT_LIGHT,
                                     font=("Helvetica", 15, "bold"))
        self.feedback_lbl.pack(pady=8)

        self.explain_lbl = tk.Label(table, text="", bg=FELT, fg=TEXT_LIGHT,
                                    font=("Menlo", 11), wraplength=760, justify="left")
        self.explain_lbl.pack(pady=(0, 8))

        # Action buttons
        btns = tk.Frame(self, bg=FELT_DARK)
        btns.pack(pady=6)
        self.hit_btn = tk.Button(btns, text="Hit", width=10, fg=BTN_TEXT,
                                 font=("Helvetica", 13, "bold"),
                                 command=lambda: self._answer("H"))
        self.stand_btn = tk.Button(btns, text="Stand", width=10, fg=BTN_TEXT,
                                   font=("Helvetica", 13, "bold"),
                                   command=lambda: self._answer("S"))
        self.dbl_btn = tk.Button(btns, text="Double", width=10, fg=BTN_TEXT,
                                 font=("Helvetica", 13, "bold"),
                                 command=lambda: self._answer("D"))
        self.split_btn = tk.Button(btns, text="Split", width=10, fg=BTN_TEXT,
                                   font=("Helvetica", 13, "bold"),
                                   command=lambda: self._answer("P"))
        self.surr_btn = tk.Button(btns, text="Surrender", width=10, fg=BTN_TEXT,
                                  font=("Helvetica", 13, "bold"),
                                  command=lambda: self._answer("R"))
        for b in (self.hit_btn, self.stand_btn, self.dbl_btn, self.split_btn, self.surr_btn):
            b.pack(side="left", padx=4)

        # Next button
        nxt = tk.Frame(self, bg=FELT_DARK)
        nxt.pack(pady=(4, 10))
        self.next_btn = tk.Button(nxt, text="Next hand (Space)",
                                  fg="#0a5c2a",
                                  font=("Helvetica", 12, "bold"),
                                  command=self.new_question)
        self.next_btn.pack()

        # Stats footer
        self.stats_lbl = tk.Label(self, text="",
                                  bg=FELT_DARK, fg=TEXT_LIGHT,
                                  font=("Helvetica", 12))
        self.stats_lbl.pack(pady=(4, 8))

        # Keyboard
        self.bind_all("<space>", self._on_space, add="+")

        self.new_question()

    # --- helpers ---
    def _clear_frame(self, frame):
        for w in frame.winfo_children():
            w.destroy()

    def _card_widget(self, parent, c: Card, small: bool = False):
        f = tk.Frame(parent, bg=FELT)
        fg = CARD_RED if c.suit in ("♥", "♦") else CARD_FG
        lbl = tk.Label(f, text=f"{c.rank}{c.suit}",
                       width=3, height=(1 if small else 2),
                       font=("Menlo", 18 if small else 22, "bold"),
                       bg=CARD_BG, fg=fg, relief="solid", bd=1, padx=4, pady=2)
        lbl.pack(padx=2, pady=2)
        return f

    def _render_situation(self):
        hand, up, cat = self.current
        self._clear_frame(self.dealer_card_frame)
        self._card_widget(self.dealer_card_frame, up).pack()
        self._clear_frame(self.player_cards_frame)
        for c in hand.cards:
            self._card_widget(self.player_cards_frame, c).pack(side="left")
        total, soft = hand.totals()
        self.player_total_lbl.config(text=f"({total}{' soft' if soft else ''})")

    def _refresh_action_availability(self):
        hand, up, cat = self.current
        rules = self.rules_getter()
        # In drills, always allow all actions if legal per rules & hand shape
        self.hit_btn.config(state="normal")
        self.stand_btn.config(state="normal")
        self.dbl_btn.config(state="normal" if hand.can_double(rules) else "disabled")
        self.split_btn.config(state="normal" if hand.can_split(rules, 1) else "disabled")
        self.surr_btn.config(state="normal" if hand.can_surrender(rules) else "disabled")

    def _stats_text(self) -> str:
        acc = (self.state.correct / self.state.attempts * 100.0) if self.state.attempts else 0.0
        return (f"Streak: {self.state.streak}   "
                f"Best: {self.state.best_streak}   "
                f"Correct: {self.state.correct}/{self.state.attempts}   "
                f"Accuracy: {acc:.1f}%")

    # --- flow ---
    def new_question(self):
        gen = GENERATORS[self.drill_name]
        hand, up, cat, _drill = gen(self.rng)
        self.current = (hand, up, cat)
        self.answered = False
        self.feedback_lbl.config(text="Pick the best action.", fg=TEXT_LIGHT)
        self.explain_lbl.config(text="")
        self._render_situation()
        self._refresh_action_availability()
        self.stats_lbl.config(text=self._stats_text())

    def _answer(self, chosen: str):
        if self.answered or not self.current:
            return
        hand, up, cat = self.current
        rules = self.rules_getter()
        devs = self.deviations_getter() or {}
        correct, bs_action, is_dev = resolve_action(hand, up.rank, rules, 1, devs)
        ok = (chosen == correct)
        self.state.attempts += 1
        if ok:
            self.state.correct += 1
            self.state.streak += 1
            self.state.best_streak = max(self.state.best_streak, self.state.streak)
            tail = ""
            if is_dev:
                tail = f"  (your deviation; BS: {ACTION_NAMES[bs_action]})"
            self.feedback_lbl.config(text=f"✓ Correct — {ACTION_NAMES[correct]}{tail}", fg=GOOD)
            self.explain_lbl.config(text="")
            sounds.play("correct")
        else:
            self.state.streak = 0
            tail = ""
            if is_dev:
                tail = f"  (your deviation; BS: {ACTION_NAMES[bs_action]})"
            self.feedback_lbl.config(
                text=f"✗ Wrong — best is {ACTION_NAMES[correct]}{tail}  (you: {ACTION_NAMES[chosen]})",
                fg=BAD,
            )
            self.explain_lbl.config(text=self._explain(hand, up, correct, rules))
            sounds.play("wrong")
        self.answered = True
        self._refresh_action_availability()
        self.stats_lbl.config(text=self._stats_text())
        # DB
        db.log_drill_attempt(
            drill=self.drill_name,
            preset_name=rules.name,
            player_cards=" ".join(str(c) for c in hand.cards),
            dealer_up=str(up),
            player_action=chosen,
            correct_action=correct,
            category=cat,
        )

    def _explain(self, hand: Hand, up: Card, correct: str, rules: Rules) -> str:
        total, soft = hand.totals()
        if hand.is_pair():
            desc = f"pair of {hand.cards[0].rank}s"
        elif soft:
            desc = f"soft {total}"
        else:
            desc = f"hard {total}"
        rules_tag = f"{rules.decks}D · {'H17' if rules.dealer_hits_soft_17 else 'S17'}"
        if rules.double_after_split:
            rules_tag += " · DAS"
        if rules.surrender != "none":
            rules_tag += f" · {rules.surrender} surrender"
        return f"{desc} vs {up.rank} → {ACTION_NAMES[correct]}    ({rules_tag})"

    def _on_space(self, _evt):
        # Only forward if visible in this tab
        if not self.winfo_ismapped():
            return
        if self.answered:
            self.new_question()


class TrainerWindow(tk.Toplevel):
    def __init__(self, parent, rules_getter, deviations_getter):
        super().__init__(parent)
        self.title("Card-Sharp — Trainer")
        self.configure(bg=FELT_DARK)
        self.transient(parent)
        self.rules_getter = rules_getter
        self.deviations_getter = deviations_getter
        self.rng = random.Random()

        # Header
        top = tk.Frame(self, bg=FELT_DARK)
        top.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(top, text="Trainer", bg=FELT_DARK, fg=TEXT_LIGHT,
                 font=("Helvetica", 16, "bold")).pack(side="left")
        self.rules_lbl = tk.Label(top, text="", bg=FELT_DARK, fg=TEXT_LIGHT,
                                  font=("Helvetica", 11))
        self.rules_lbl.pack(side="right")
        self._refresh_rules_label()

        # Notebook of drill tabs
        style = ttk.Style(self)
        try:
            style.theme_use("aqua")
        except Exception:
            pass

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=8)
        self.tabs: dict[str, DrillTab] = {}
        for name in DRILL_ORDER:
            tab = DrillTab(nb, name, self.rules_getter, self.deviations_getter, self.rng)
            self.tabs[name] = tab
            label = {
                "hard": "Hard totals",
                "soft": "Soft (A,2–A,9)",
                "splits": "Splits",
                "doubles": "Doubles",
                "surrender": "Surrender",
                "mixed": "Mixed",
            }.get(name, name)
            nb.add(tab, text=label)

        center(self, 900, 620)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _refresh_rules_label(self):
        r = self.rules_getter()
        self.rules_lbl.config(
            text=f"Preset: {r.name}  ·  {r.decks}D · "
                 f"{'H17' if r.dealer_hits_soft_17 else 'S17'} · "
                 f"{'DAS' if r.double_after_split else 'no DAS'} · "
                 f"surrender: {r.surrender}"
        )
