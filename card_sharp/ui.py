import math
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from typing import Optional

from . import APP_NAME, __version__
from .engine import Game, Hand, Card, card_value
from .rules import Rules, PRESETS
from .strategy import basic_strategy, resolve_action, ACTION_NAMES
from . import prefs, db, sounds
from .rules_editor import RulesEditor
from .trainer import TrainerWindow
from .stats import StatsWindow
from .overrides_editor import DeviationsEditor
from .table_window import TableWindow


FELT = "#0b6b3a"
FELT_DARK = "#083f22"
CARD_BG = "#f7f2e7"
CARD_FG = "#111111"
CARD_RED = "#c02020"
TEXT_LIGHT = "#f2f2f2"
BTN_TEXT = "#111111"        # macOS Tk buttons render as white Aqua; text must be dark
BTN_TEXT_ACCENT = "#0a5c2a" # dark green for "Deal" / "Next hand" — readable on white face
GOOD = "#4caf50"
BAD = "#e53935"
WARN = "#ffb74d"
RAIL = "#2c1608"
GOLD = "#d4a843"
AUTO_DEAL_DELAY_MS = 4000


def center_window(win: tk.Toplevel | tk.Tk, w: int, h: int):
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 3
    win.geometry(f"{w}x{h}+{x}+{y}")


def card_color(c: Card) -> str:
    return CARD_RED if c.suit in ("♥", "♦") else CARD_FG


def resource_path(*parts: str) -> str:
    """Find a bundled asset in py2app, or the project asset during development."""
    if getattr(sys, "frozen", False):
        base = os.path.join(os.path.dirname(sys.executable), "..", "Resources")
    else:
        base = os.path.join(os.path.dirname(__file__), "..", "assets")
    return os.path.normpath(os.path.join(base, *parts))


@dataclass
class DecisionRecord:
    step: int
    player_cards: str
    dealer_up: str
    player_action: str
    correct_action: str          # accepted answer (may be your deviation)
    bs_action: str = ""          # what pure basic strategy says
    is_deviation: bool = False


class CardWidget(tk.Frame):
    def __init__(self, parent, card: Optional[Card] = None, hidden: bool = False):
        super().__init__(parent, bg=FELT, bd=0, highlightthickness=0)
        self.card = card
        self.hidden = hidden
        self._label = tk.Label(
            self, text="", width=3, height=2,
            font=("Menlo", 22, "bold"),
            bg=CARD_BG, fg=CARD_FG,
            relief="solid", bd=1, padx=6, pady=2,
        )
        self._label.pack(padx=3, pady=3)
        self.refresh()

    def refresh(self):
        if self.hidden or self.card is None:
            self._label.config(text="🂠", bg="#334", fg="#eee")
        else:
            self._label.config(text=f"{self.card.rank}{self.card.suit}",
                               bg=CARD_BG, fg=card_color(self.card))


class HandFrame(tk.Frame):
    def __init__(self, parent, title: str = ""):
        super().__init__(parent, bg=FELT)
        self.title = title
        self.title_lbl = tk.Label(self, text=title, bg=FELT, fg=TEXT_LIGHT,
                                  font=("Helvetica", 13, "bold"))
        self.title_lbl.pack(anchor="w", padx=8, pady=(4, 0))
        self.cards_frame = tk.Frame(self, bg=FELT)
        self.cards_frame.pack(padx=6, pady=4, anchor="w")
        self.total_lbl = tk.Label(self, text="", bg=FELT, fg=TEXT_LIGHT,
                                  font=("Helvetica", 12))
        self.total_lbl.pack(anchor="w", padx=8, pady=(0, 4))

    def render(self, hand: Hand, hide_first: bool = False, show_total: bool = True, active: bool = False):
        for w in self.cards_frame.winfo_children():
            w.destroy()
        for i, c in enumerate(hand.cards):
            hidden = (hide_first and i == 0)
            CardWidget(self.cards_frame, c, hidden=hidden).pack(side="left")
        if show_total and hand.cards:
            total, soft = hand.totals()
            txt = f"Total: {total}{' (soft)' if soft else ''}"
            if hand.is_blackjack():
                txt = "BLACKJACK!"
            self.total_lbl.config(text=txt)
        else:
            self.total_lbl.config(text="Total: ?")
        border = 3 if active else 0
        self.config(highlightthickness=border, highlightbackground=WARN)

    def set_title(self, t: str):
        self.title_lbl.config(text=t)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {__version__}")
        self.configure(bg=FELT_DARK)
        self.prefs = prefs.load()

        # Rules from prefs (custom presets stored separately)
        preset_name = self.prefs.get("preset_name") or "Foxwoods — 6D Main Pit"
        self.rules = self._load_preset(preset_name)

        self.game = Game(self.rules, starting_bankroll=int(self.prefs.get("bankroll", 1000)))
        self.session_id = db.start_session(self.rules.name, self.game.bankroll)
        self.session_starting_bankroll = self.game.bankroll
        self.hands_played = 0
        self.hands_won = 0
        self.correct_moves = 0
        self.total_moves = 0

        # Track decisions this hand for review panel
        self.current_hand_decisions: list[DecisionRecord] = []
        self.step_counter = 0
        self.auto_deal_after_id: Optional[str] = None
        self.auto_deal_seconds_left = 0

        self._build_ui()
        self._apply_geometry()
        self._refresh_status()
        self._show_between_rounds()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- preset handling --
    def _load_preset(self, name: str) -> Rules:
        custom = self.prefs.get("custom_presets", {})
        if name in custom:
            try:
                return Rules.from_dict(custom[name])
            except Exception:
                pass
        if name in PRESETS:
            return PRESETS[name]
        return PRESETS["Foxwoods — 6D Main Pit"]

    def _apply_geometry(self):
        # Always center on launch (preserve prior size only, not position)
        default_w, default_h = 1180, 760
        geom = self.prefs.get("window_geometry", f"{default_w}x{default_h}+200+120")
        w, h = default_w, default_h
        try:
            size_part = geom.split("+")[0]
            ws, hs = size_part.split("x")
            w, h = int(ws), int(hs)
        except Exception:
            pass
        # Never shrink below the size the toolbar needs — an old saved
        # geometry from a smaller default (or a manual resize) would
        # otherwise reintroduce the crowded/clipped toolbar.
        w = max(w, default_w)
        h = max(h, default_h)
        self.minsize(default_w, default_h)
        center_window(self, w, h)

    # -- UI construction --
    def _build_ui(self):
        # Info bar: subtle visual identity + preset summary / live session stats.
        info = tk.Frame(self, bg=FELT_DARK)
        info.pack(side="top", fill="x", padx=10, pady=(8, 2))

        self.table_badge = None
        try:
            self.table_badge = tk.PhotoImage(file=resource_path("table-badge.png"))
            tk.Label(info, image=self.table_badge, bg=FELT_DARK).pack(side="left", padx=(0, 8))
        except tk.TclError:
            # The app remains fully usable if a locally-built asset is absent.
            pass

        self.preset_lbl = tk.Label(info, text="", bg=FELT_DARK, fg=TEXT_LIGHT,
                                   font=("Helvetica", 13, "bold"))
        self.preset_lbl.pack(side="left")

        self.stats_lbl = tk.Label(info, text="", bg=FELT_DARK, fg=TEXT_LIGHT,
                                  font=("Helvetica", 12))
        self.stats_lbl.pack(side="right")

        # Toolbar: grouped action buttons on their own row, separate from
        # the info labels above — keeps either row from crowding the other.
        toolbar = tk.Frame(self, bg=FELT_DARK)
        toolbar.pack(side="top", fill="x", padx=10, pady=(0, 8))

        windows_grp = tk.Frame(toolbar, bg=FELT_DARK)
        windows_grp.pack(side="left")
        for text, cmd in (
            ("Rules…", self._open_rules),
            ("Table Play…", self._open_table),
            ("Trainer…", self._open_trainer),
            ("Stats…", self._open_stats),
            ("Deviations…", self._open_deviations),
        ):
            ttk.Button(windows_grp, text=text, command=cmd).pack(side="left", padx=(0, 6))

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        game_grp = tk.Frame(toolbar, bg=FELT_DARK)
        game_grp.pack(side="left")
        ttk.Button(game_grp, text="New shoe", command=self._new_shoe).pack(side="left", padx=(0, 6))
        ttk.Button(game_grp, text="Reset bankroll", command=self._reset_bankroll).pack(side="left", padx=(0, 6))
        self.sound_var = tk.BooleanVar(value=bool(self.prefs.get("sound_enabled", True)))
        sounds.ENABLED = self.sound_var.get()
        self.sound_chk = tk.Checkbutton(game_grp, text="Sound",
                                        variable=self.sound_var,
                                        bg=FELT_DARK, fg=TEXT_LIGHT,
                                        selectcolor=FELT_DARK,
                                        activebackground=FELT_DARK,
                                        activeforeground=TEXT_LIGHT,
                                        command=self._toggle_sound)
        self.sound_chk.pack(side="left", padx=4)
        self.auto_deal_var = tk.BooleanVar(value=bool(self.prefs.get("auto_deal", False)))
        self.auto_deal_chk = tk.Checkbutton(
            game_grp, text="Auto Deal", variable=self.auto_deal_var,
            bg=FELT_DARK, fg=TEXT_LIGHT, selectcolor=FELT_DARK,
            activebackground=FELT_DARK, activeforeground=TEXT_LIGHT,
            command=self._toggle_auto_deal,
        )
        self.auto_deal_chk.pack(side="left", padx=4)

        ttk.Button(toolbar, text="Help", command=self._show_help).pack(side="right")

        # Table area — canvas with casino felt
        self.table_canvas = tk.Canvas(self, bg=RAIL, highlightthickness=0)
        self.table_canvas.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.dealer_frame = HandFrame(self.table_canvas, title="Dealer")
        self.player_area = tk.Frame(self.table_canvas, bg=FELT)
        self.player_hand_frames: list[HandFrame] = []
        self.msg_lbl = tk.Label(self.table_canvas, text="", bg=FELT, fg=TEXT_LIGHT,
                                font=("Helvetica", 14, "bold"))
        self._cw_ids: dict = {}
        self.table_canvas.bind("<Configure>", self._redraw_felt)

        # Controls
        controls = tk.Frame(self, bg=FELT_DARK)
        controls.pack(side="top", fill="x", padx=10, pady=(0, 4))

        # Bet frame (visible between rounds) — two rows: bet controls on top, Deal below
        self.bet_frame = tk.Frame(controls, bg=FELT_DARK)
        bet_row = tk.Frame(self.bet_frame, bg=FELT_DARK)
        bet_row.pack(anchor="w")
        tk.Label(bet_row, text="Bet:", bg=FELT_DARK, fg=TEXT_LIGHT,
                 font=("Helvetica", 12)).pack(side="left")
        self.bet_var = tk.IntVar(value=int(self.prefs.get("bet", 25)))
        self.bet_entry = tk.Entry(bet_row, textvariable=self.bet_var, width=8,
                                  bg="white", fg="black", insertbackground="black",
                                  font=("Helvetica", 12))
        self.bet_entry.pack(side="left", padx=6)
        self.bet_entry.bind("<KeyPress>", self._cancel_auto_deal_for_bet)
        for amt in (5, 25, 100, 500):
            tk.Button(bet_row, text=f"${amt}", fg=BTN_TEXT,
                      command=lambda a=amt: self._set_bet(a)).pack(side="left", padx=2)

        deal_row = tk.Frame(self.bet_frame, bg=FELT_DARK)
        deal_row.pack(anchor="w", pady=(6, 0))
        self.deal_btn = tk.Button(deal_row, text="Deal",
                                  fg=BTN_TEXT_ACCENT,
                                  font=("Helvetica", 14, "bold"),
                                  width=14,
                                  command=self._deal)
        self.deal_btn.pack(side="left")

        # Action frame (visible during round)
        self.action_frame = tk.Frame(controls, bg=FELT_DARK)
        self.hit_btn = tk.Button(self.action_frame, text="Hit",     width=10, fg=BTN_TEXT, command=lambda: self._player_action("H"))
        self.stand_btn = tk.Button(self.action_frame, text="Stand", width=10, fg=BTN_TEXT, command=lambda: self._player_action("S"))
        self.dbl_btn = tk.Button(self.action_frame, text="Double",  width=10, fg=BTN_TEXT, command=lambda: self._player_action("D"))
        self.split_btn = tk.Button(self.action_frame, text="Split", width=10, fg=BTN_TEXT, command=lambda: self._player_action("P"))
        self.surr_btn = tk.Button(self.action_frame, text="Surrender", width=10, fg=BTN_TEXT, command=lambda: self._player_action("R"))
        for b in (self.hit_btn, self.stand_btn, self.dbl_btn, self.split_btn, self.surr_btn):
            b.configure(font=("Helvetica", 13, "bold"))
            b.pack(side="left", padx=4)

        # Between-rounds: Next hand button
        self.next_frame = tk.Frame(controls, bg=FELT_DARK)
        self.next_btn = tk.Button(self.next_frame, text="Next hand",
                                  fg=BTN_TEXT_ACCENT,
                                  font=("Helvetica", 13, "bold"),
                                  command=self._show_between_rounds)
        self.next_btn.pack(side="left", padx=12)

        # Review panel
        review = tk.LabelFrame(self, text="Hand review (basic strategy)",
                               bg=FELT_DARK, fg=TEXT_LIGHT,
                               font=("Helvetica", 12, "bold"))
        review.pack(side="bottom", fill="x", padx=10, pady=8)
        self.review_text = tk.Text(review, height=6, bg="#111", fg=TEXT_LIGHT,
                                   insertbackground=TEXT_LIGHT,
                                   font=("Menlo", 12), wrap="word")
        self.review_text.pack(fill="x", padx=6, pady=6)
        self.review_text.tag_config("good", foreground=GOOD)
        self.review_text.tag_config("bad", foreground=BAD)
        self.review_text.tag_config("neut", foreground=TEXT_LIGHT)
        self.review_text.tag_config("warn", foreground=WARN)
        self.review_text.tag_config("head", foreground=WARN, font=("Menlo", 12, "bold"))

    # -- status --
    def _refresh_status(self):
        self.preset_lbl.config(text=f"Preset: {self.rules.name}   "
                                    f"({self.rules.decks}D · "
                                    f"{'H17' if self.rules.dealer_hits_soft_17 else 'S17'} · "
                                    f"{'DAS' if self.rules.double_after_split else 'no DAS'} · "
                                    f"BJ {int(self.rules.blackjack_payout*10)}:10 · "
                                    f"Surr: {self.rules.surrender})")
        acc = (self.correct_moves / self.total_moves * 100.0) if self.total_moves else 0.0
        win_pct = (self.hands_won / self.hands_played * 100.0) if self.hands_played else 0.0
        net = self.game.bankroll - self.session_starting_bankroll
        remaining = max(0, self.game.shoe.cut_index - self.game.shoe.dealt_count())
        self.stats_lbl.config(text=(f"Bankroll: ${self.game.bankroll}   "
                                    f"Won: {'+' if net>=0 else ''}${net}   "
                                    f"Hands: {self.hands_played}   "
                                    f"Win%: {win_pct:.1f}%   "
                                    f"BS Acc: {acc:.1f}%   "
                                    f"Shoe: {remaining} cards to cut"))

    def _redraw_felt(self, event=None):
        c = self.table_canvas
        w, h = c.winfo_width(), c.winfo_height()
        if w < 100 or h < 100:
            return
        c.delete("felt")

        cx = w / 2
        pad = 12
        rx = (w - 2 * pad) / 2
        curve_depth = h * 0.32
        straight_y = h - pad - curve_depth

        pts = [(pad, pad), (w - pad, pad), (w - pad, straight_y)]
        for i in range(101):
            a = math.pi * i / 100
            pts.append((cx + rx * math.cos(a),
                        straight_y + curve_depth * math.sin(a)))
        pts.append((pad, straight_y))
        flat = []
        for px, py in pts:
            flat.extend([px, py])
        c.create_polygon(flat, fill=FELT, outline="#064d24", width=4, tags="felt")
        # A second thin inlay gives the table more depth without competing with cards.
        c.create_arc(pad + 10, pad + 10, w - pad - 10, h * 1.20,
                     start=205, extent=130, style="arc", outline="#3d9863",
                     width=1, tags="felt")

        payout = "3 TO 2" if self.rules.blackjack_payout >= 1.5 else "6 TO 5"
        c.create_text(cx, h * 0.27,
                      text=f"BLACKJACK PAYS {payout}",
                      fill=GOLD, font=("Helvetica", 15, "bold italic"), tags="felt")
        dealer_txt = ("DEALER MUST HIT SOFT 17" if self.rules.dealer_hits_soft_17
                      else "DEALER MUST STAND ON ALL 17s")
        c.create_text(cx, h * 0.34, text=dealer_txt,
                      fill=GOLD, font=("Helvetica", 11), tags="felt")

        ins_y = h * 0.42
        ins_rx = rx * 0.60
        ins_pts = []
        for i in range(51):
            a = math.pi * i / 50
            ins_pts.extend([cx + ins_rx * math.cos(a),
                            ins_y + curve_depth * 0.10 * math.sin(a)])
        c.create_line(ins_pts, fill=GOLD, width=1.5, dash=(8, 4),
                      smooth=True, tags="felt")
        c.create_text(cx, ins_y - 8,
                      text="INSURANCE PAYS 2 TO 1",
                      fill=GOLD, font=("Helvetica", 9), tags="felt")

        r = min(24, h * 0.06)
        bet_y = h * 0.53
        c.create_oval(cx - r, bet_y - r, cx + r, bet_y + r,
                      outline=GOLD, width=2, fill="#0a5a31", tags="felt")
        c.create_oval(cx - r + 5, bet_y - r + 5, cx + r - 5, bet_y + r - 5,
                      outline="#f4d77d", width=1, tags="felt")

        if not self._cw_ids:
            self._cw_ids["dealer"] = c.create_window(
                cx, h * 0.08, window=self.dealer_frame, anchor="n")
            self._cw_ids["msg"] = c.create_window(
                cx, h * 0.62, window=self.msg_lbl, anchor="n")
            self._cw_ids["player"] = c.create_window(
                cx, h * 0.72, window=self.player_area, anchor="n")
        else:
            c.coords(self._cw_ids["dealer"], cx, h * 0.08)
            c.coords(self._cw_ids["msg"], cx, h * 0.62)
            c.coords(self._cw_ids["player"], cx, h * 0.72)
        self._update_bet_display()

    def _update_bet_display(self):
        c = self.table_canvas
        c.delete("bet_amt")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 100:
            return
        bet_y = h * 0.53
        if hasattr(self, "game") and self.game.in_round and self.game.player_hands:
            total_bet = sum(hnd.bet for hnd in self.game.player_hands)
            c.create_text(w / 2, bet_y, text=f"${total_bet}",
                          fill=GOLD, font=("Helvetica", 10, "bold"), tags="bet_amt")

    # -- flow --
    def _show_between_rounds(self):
        self._cancel_auto_deal()
        # Clear round display
        self.msg_lbl.config(text="Place your bet and click Deal.")
        for f in self.player_hand_frames:
            f.destroy()
        self.player_hand_frames = []
        self.dealer_frame.render(Hand(), show_total=False)
        # Show bet controls
        self.action_frame.pack_forget()
        self.next_frame.pack_forget()
        self.bet_frame.pack(side="left")
        self.deal_btn.config(state="normal")
        self.bet_entry.config(state="normal")
        self._update_bet_display()

    def _show_playing(self):
        self.bet_frame.pack_forget()
        self.next_frame.pack_forget()
        self.action_frame.pack(side="left")

    def _show_finished(self):
        # Keep betting controls available while Auto Deal is counting down.
        # Changing a bet is an explicit signal to stop the pending hand.
        self.bet_frame.pack(side="left")
        self.deal_btn.config(state="normal")
        self.bet_entry.config(state="normal")
        self.action_frame.pack_forget()
        self.next_frame.pack(side="left")
        if self.auto_deal_var.get() and self.game.bankroll > 0:
            self._start_auto_deal()

    def _deal(self):
        self._cancel_auto_deal()
        try:
            bet = int(self.bet_var.get())
        except Exception:
            messagebox.showerror("Invalid bet", "Enter a whole-number bet.")
            return
        if bet <= 0:
            messagebox.showerror("Invalid bet", "Bet must be greater than 0.")
            return
        if bet > self.game.bankroll:
            messagebox.showerror("Insufficient bankroll", f"You only have ${self.game.bankroll}.")
            return
        self.prefs["bet"] = bet
        # New round
        self.current_hand_decisions = []
        self.step_counter = 0
        self.game.start_round(bet)
        self._render_table(hide_dealer=True)
        self.msg_lbl.config(text="Your move.")
        self._show_playing()
        self._update_action_availability()
        # Clear review of prior hand
        self.review_text.delete("1.0", "end")

    def _set_bet(self, amount: int):
        self._cancel_auto_deal_for_bet()
        self.bet_var.set(amount)

    def _toggle_auto_deal(self):
        self.prefs["auto_deal"] = bool(self.auto_deal_var.get())
        prefs.save(self.prefs)
        if not self.auto_deal_var.get():
            self._cancel_auto_deal()

    def _start_auto_deal(self):
        self._cancel_auto_deal()
        self.auto_deal_seconds_left = AUTO_DEAL_DELAY_MS // 1000
        self._update_auto_deal_message()
        self.auto_deal_after_id = self.after(1000, self._auto_deal_tick)

    def _auto_deal_tick(self):
        self.auto_deal_after_id = None
        self.auto_deal_seconds_left -= 1
        if self.auto_deal_seconds_left <= 0:
            self._deal()
            return
        self._update_auto_deal_message()
        self.auto_deal_after_id = self.after(1000, self._auto_deal_tick)

    def _update_auto_deal_message(self):
        self.msg_lbl.config(
            text=f"Next hand in {self.auto_deal_seconds_left}s — change your bet to pause Auto Deal."
        )

    def _cancel_auto_deal_for_bet(self, event=None):
        if self.auto_deal_after_id is not None:
            self._cancel_auto_deal()
            self.msg_lbl.config(text="Auto Deal paused — wager adjusted. Click Deal when ready.")

    def _cancel_auto_deal(self):
        if self.auto_deal_after_id is not None:
            try:
                self.after_cancel(self.auto_deal_after_id)
            except tk.TclError:
                pass
        self.auto_deal_after_id = None
        self.auto_deal_seconds_left = 0

    def _render_table(self, hide_dealer: bool):
        # Dealer
        self.dealer_frame.render(self.game.dealer_hand,
                                 hide_first=hide_dealer,
                                 show_total=not hide_dealer)
        # Player hands
        for f in self.player_hand_frames:
            f.destroy()
        self.player_hand_frames = []
        for i, h in enumerate(self.game.player_hands):
            title = f"You (${h.bet})" if len(self.game.player_hands) == 1 else f"Hand {i+1} (${h.bet})"
            frame = HandFrame(self.player_area, title=title)
            active = (i == self.game.active_hand_index) and self.game.in_round and not self.game.all_hands_done()
            frame.render(h, active=active)
            frame.pack(side="left", padx=8, anchor="n")
            self.player_hand_frames.append(frame)
        self._update_bet_display()

    def _update_action_availability(self):
        h = self.game.active_hand()
        self.hit_btn.config(state="normal")
        self.stand_btn.config(state="normal")
        self.dbl_btn.config(state="normal" if h.can_double(self.rules) and self.game.bankroll >= h.bet else "disabled")
        self.split_btn.config(state="normal" if h.can_split(self.rules, len(self.game.player_hands)) and self.game.bankroll >= h.bet else "disabled")
        self.surr_btn.config(state="normal" if h.can_surrender(self.rules) else "disabled")

    def _player_action(self, action: str):
        # Record player's choice + basic strategy suggestion.
        # UI convention: dealer.cards[0] is hidden (hole), cards[1] is the visible upcard.
        # Strategy MUST be computed against the visible upcard.
        h = self.game.active_hand()
        dealer_up = self.game.dealer_upcard().rank
        correct, bs_action, is_dev = resolve_action(
            h, dealer_up, self.rules, len(self.game.player_hands),
            self.prefs.get("deviations", {}),
        )
        player_cards_str = " ".join(str(c) for c in h.cards)

        self.step_counter += 1
        self.current_hand_decisions.append(DecisionRecord(
            step=self.step_counter,
            player_cards=player_cards_str,
            dealer_up=dealer_up,
            player_action=action,
            correct_action=correct,
            bs_action=bs_action,
            is_deviation=is_dev,
        ))
        self.total_moves += 1
        if action == correct:
            self.correct_moves += 1
            sounds.play("correct")
        else:
            sounds.play("wrong")

        # Execute the action
        try:
            if action == "H":
                self.game.hit()
            elif action == "S":
                self.game.stand()
            elif action == "D":
                if not h.can_double(self.rules) or self.game.bankroll < h.bet:
                    messagebox.showinfo("Not allowed", "Double is not allowed here.")
                    return
                self.game.double()
            elif action == "P":
                if not h.can_split(self.rules, len(self.game.player_hands)) or self.game.bankroll < h.bet:
                    messagebox.showinfo("Not allowed", "Split is not allowed here.")
                    return
                self.game.split()
            elif action == "R":
                if not h.can_surrender(self.rules):
                    messagebox.showinfo("Not allowed", "Surrender is not allowed here.")
                    return
                self.game.surrender()
        except AssertionError as e:
            messagebox.showerror("Illegal move", str(e))
            return

        # Continue round or resolve
        self._render_table(hide_dealer=True)
        if self.game.all_hands_done():
            self._resolve_round()
        else:
            self._update_action_availability()

    def _resolve_round(self):
        self.game.dealer_play()
        results = self.game.settle()
        self._render_table(hide_dealer=False)
        self.hands_played += 1

        # Assemble outcome message. Count a "hand win" for the round if the
        # net payout across all sub-hands (splits, doubles) is positive.
        outcomes = []
        net = 0
        any_bj = False
        any_win = False
        any_lose = False
        for r in results:
            outcomes.append(f"{r.outcome.upper()} ({'+' if r.payout>=0 else ''}${r.payout})")
            net += r.payout
            if r.outcome == "blackjack":
                any_bj = True
            elif r.outcome == "win":
                any_win = True
            elif r.outcome in ("lose", "surrender"):
                any_lose = True
        if net > 0:
            self.hands_won += 1
        self.msg_lbl.config(text="  |  ".join(outcomes) + f"    Net: {'+' if net>=0 else ''}${net}")

        # Play a settlement sound: BJ > win > push > lose
        if any_bj:
            sounds.play("bj")
        elif any_win and net > 0:
            sounds.play("win")
        elif any_lose and net < 0:
            sounds.play("lose")
        else:
            sounds.play("push")

        # DB logging
        dealer_str = " ".join(str(c) for c in self.game.dealer_hand.cards)
        for i, r in enumerate(results):
            player_str = " ".join(str(c) for c in r.hand.cards)
            hid = db.log_hand(self.session_id, r.hand.bet,
                              self.game.dealer_upcard().rank,
                              dealer_str, player_str, r.outcome, r.payout)
            for d in self.current_hand_decisions:
                db.log_decision(hid, d.step, d.player_cards, d.dealer_up,
                                d.player_action, d.correct_action)
                # If this decision used a personal deviation, record it against the
                # actual hand outcome so the user can measure whether their exception pays.
                if d.is_deviation and d.player_action == d.correct_action:
                    from . import overrides as _ov
                    # Rebuild the hand key from the decision snapshot for aggregation.
                    hk = self._recover_hand_key_from_snapshot(d.player_cards)
                    if hk:
                        db.log_deviation_event(
                            hand_key=hk,
                            upcard=_ov.upcard_key(d.dealer_up),
                            chosen_action=d.player_action,
                            bs_action=d.bs_action,
                            hand_outcome=r.outcome,
                            hand_payout=r.payout,
                        )

        # Review panel
        self._render_review()

        # Bankroll persist
        self.prefs["bankroll"] = self.game.bankroll
        prefs.save(self.prefs)
        db.end_session(self.session_id, self.game.bankroll,
                       self.hands_played, self.correct_moves, self.total_moves)

        self._refresh_status()

        if self.game.bankroll <= 0:
            self.msg_lbl.config(text="Bankroll gone. Use 'Reset bankroll' to keep playing.")

        self._show_finished()

    def _render_review(self):
        self.review_text.delete("1.0", "end")
        if not self.current_hand_decisions:
            self.review_text.insert("end", "(no decisions this hand)\n", "neut")
            return
        self.review_text.insert("end",
            f"{'#':<3}{'Your hand':<18}{'Up':<4}{'You':<10}{'Best':<10}Result\n",
            "head")
        for d in self.current_hand_decisions:
            you = ACTION_NAMES.get(d.player_action, d.player_action)
            best = ACTION_NAMES.get(d.correct_action, d.correct_action)
            ok = (d.player_action == d.correct_action)
            mark = "✓ correct" if ok else "✗ wrong"
            tag = "good" if ok else "bad"
            self.review_text.insert("end",
                f"{d.step:<3}{d.player_cards:<18}{d.dealer_up:<4}{you:<10}{best:<10}",
                "neut")
            self.review_text.insert("end", f"{mark}", tag)
            if d.is_deviation:
                bs_name = ACTION_NAMES.get(d.bs_action, d.bs_action)
                self.review_text.insert("end", f"   (your deviation; BS: {bs_name})", "warn")
            self.review_text.insert("end", "\n", "neut")

    # -- menu actions --
    def _open_trainer(self):
        w = TrainerWindow(self,
                          rules_getter=lambda: self.rules,
                          deviations_getter=lambda: self.prefs.get("deviations", {}))
        w.focus_set()

    def _open_table(self):
        w = TableWindow(self, rules_getter=lambda: self.rules)
        w.focus_set()

    def _show_help(self):
        msg = (
            "Card-Sharp — Quick guide\n\n"
            "  •  Solo sim (this window): deal hands, get post-hand review vs. basic strategy.\n"
            "  •  Table Play: sit at a table with 2-6 seats. Pick each other seat's personality\n"
            "     (basic, tight, aggressive, random, wreck, moron). Watch how they change the\n"
            "     cards you and the dealer draw. Every action is logged.\n"
            "  •  Trainer: drill hard totals / soft hands / splits / doubles / surrender / mixed.\n"
            "     Instant feedback with the correct answer for the current rule set.\n"
            "  •  Deviations: encode your personal exceptions (e.g. 'double hard 8 vs 5').\n"
            "     The reviewer accepts your deviation as correct and shows what BS says.\n"
            "  •  Stats: overall accuracy, per-drill/per-category breakdowns, top mistakes,\n"
            "     recent sessions, and per-deviation win/loss + net $ so you can see whether\n"
            "     your exceptions actually pay.\n"
            "  •  Rules: switch between casino presets or edit any rule for a custom preset.\n\n"
            "Keyboard (Table Play): H/S/D/P/R for actions.\n"
        )
        messagebox.showinfo("Card-Sharp — Help", msg)

    def _recover_hand_key_from_snapshot(self, cards_str: str) -> str | None:
        """Rebuild an overrides hand_key from a snapshot like '8♠ 5♦' or '8♠ 5♦ 2♥'."""
        from . import overrides as _ov
        parts = cards_str.split()
        h = Hand()
        for tok in parts:
            if not tok:
                continue
            # Rank is everything before the suit glyph (last char).
            rank = tok[:-1]
            if rank not in ("A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K"):
                return None
            h.add(Card(rank, "♠"))
        return _ov.hand_key(h) if h.cards else None

    def _open_deviations(self):
        def on_save(new_devs):
            self.prefs["deviations"] = new_devs
            prefs.save(self.prefs)
        w = DeviationsEditor(self, self.prefs.get("deviations", {}), on_save)
        w.focus_set()

    def _open_stats(self):
        w = StatsWindow(self)
        w.focus_set()

    def _toggle_sound(self):
        sounds.ENABLED = self.sound_var.get()
        self.prefs["sound_enabled"] = self.sound_var.get()
        prefs.save(self.prefs)

    def _open_rules(self):
        current_custom = dict(self.prefs.get("custom_presets", {}))
        dlg = RulesEditor(self, self.rules, current_custom)
        self.wait_window(dlg)
        if dlg.result is not None:
            new_rules, updated_custom, chosen_name = dlg.result
            self.rules = new_rules
            self.prefs["preset_name"] = chosen_name
            self.prefs["custom_presets"] = updated_custom
            prefs.save(self.prefs)
            # New rules => new game shoe (deck count could change)
            self.game = Game(self.rules, starting_bankroll=self.game.bankroll)
            self.session_id = db.start_session(self.rules.name, self.game.bankroll)
            self.session_starting_bankroll = self.game.bankroll
            self.hands_played = 0
            self.hands_won = 0
            self.correct_moves = 0
            self.total_moves = 0
            self._refresh_status()
            self._show_between_rounds()
            self._redraw_felt()

    def _new_shoe(self):
        self.game.new_shoe()
        self._refresh_status()
        messagebox.showinfo("New shoe", "Fresh shoe shuffled.")

    def _reset_bankroll(self):
        self.game.bankroll = 1000
        self.prefs["bankroll"] = 1000
        self.session_starting_bankroll = 1000
        self.hands_played = 0
        self.hands_won = 0
        prefs.save(self.prefs)
        self._refresh_status()

    def _on_close(self):
        self.prefs["window_geometry"] = self.geometry()
        self.prefs["bankroll"] = self.game.bankroll
        prefs.save(self.prefs)
        db.end_session(self.session_id, self.game.bankroll,
                       self.hands_played, self.correct_moves, self.total_moves)
        self.destroy()


def run():
    app = App()
    app.mainloop()
