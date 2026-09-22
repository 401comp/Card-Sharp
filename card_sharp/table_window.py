import math
import random
import tkinter as tk
from tkinter import ttk, messagebox

from .engine import Hand, Card
from .rules import Rules
from .table_game import Table, Seat, npc_action, PERSONALITIES, PERSONALITY_DESC
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
YOUR_HL = "#ffd54f"
RAIL = "#2c1608"
GOLD = "#d4a843"


def center(win, w, h):
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//3}")


def _card_widget(parent, c: Card, hidden: bool = False):
    frame = tk.Frame(parent, bg=FELT, bd=0, highlightthickness=0)
    if hidden:
        lbl = tk.Label(frame, text="🂠", width=3, height=1,
                       font=("Menlo", 18, "bold"),
                       bg="#334", fg="#eee",
                       relief="solid", bd=1, padx=4, pady=1)
    else:
        fg = CARD_RED if c.suit in ("♥", "♦") else CARD_FG
        lbl = tk.Label(frame, text=f"{c.rank}{c.suit}", width=3, height=1,
                       font=("Menlo", 18, "bold"),
                       bg=CARD_BG, fg=fg,
                       relief="solid", bd=1, padx=4, pady=1)
    lbl.pack(padx=2, pady=2)
    return frame


class TableWindow(tk.Toplevel):
    """Multi-seat table game. Starts on the Setup screen; Deal moves to Play."""

    def __init__(self, parent, rules_getter):
        super().__init__(parent)
        self.title("Card-Sharp — Table Play")
        self.configure(bg=FELT_DARK)
        self.transient(parent)
        self.rules_getter = rules_getter
        self.rng = random.Random()

        self.table: Table | None = None
        self.you_seat_index: int = 0
        self.between_rounds: bool = True
        self.setup_frame: tk.Frame | None = None
        self.play_frame: tk.Frame | None = None

        self._build_setup()
        center(self, 1000, 700)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # ---- setup screen ----
    def _build_setup(self):
        if self.play_frame:
            self.play_frame.destroy()
            self.play_frame = None
        self.setup_frame = tk.Frame(self, bg=FELT_DARK)
        self.setup_frame.pack(fill="both", expand=True, padx=14, pady=12)

        tk.Label(self.setup_frame, text="Table setup", bg=FELT_DARK, fg=WARN,
                 font=("Helvetica", 16, "bold")).pack(anchor="w")
        tk.Label(self.setup_frame,
                 text=("Seat other players around you — see how the table dynamic changes.\n"
                       "Mark exactly one seat as 'You' — that's the one you'll control."),
                 bg=FELT_DARK, fg=TEXT_LIGHT,
                 font=("Helvetica", 11), justify="left").pack(anchor="w", pady=(2, 10))

        # Seat count
        top = tk.Frame(self.setup_frame, bg=FELT_DARK)
        top.pack(anchor="w", pady=(0, 6))
        tk.Label(top, text="Number of seats:", bg=FELT_DARK, fg=TEXT_LIGHT,
                 font=("Helvetica", 12)).pack(side="left")
        self.n_seats_var = tk.IntVar(value=3)
        ttk.Combobox(top, textvariable=self.n_seats_var, values=[2, 3, 4, 5, 6],
                     state="readonly", width=5).pack(side="left", padx=6)
        tk.Button(top, text="Apply seat count", fg=BTN_TEXT,
                  command=self._rebuild_seat_rows).pack(side="left", padx=8)

        # Header row
        hdr = tk.Frame(self.setup_frame, bg=FELT_DARK)
        hdr.pack(fill="x", pady=(10, 2))
        for lbl, w in (("Seat", 6), ("Name", 22), ("Personality", 24), ("Description", 42), ("You?", 6)):
            tk.Label(hdr, text=lbl, bg=FELT_DARK, fg=WARN,
                     font=("Helvetica", 11, "bold"), width=w, anchor="w").pack(side="left")

        # Seat rows container
        self.rows_frame = tk.Frame(self.setup_frame, bg=FELT_DARK)
        self.rows_frame.pack(fill="x")
        self.seat_widgets: list[dict] = []
        self.you_var = tk.IntVar(value=0)
        self._rebuild_seat_rows()

        # Bet
        bet_row = tk.Frame(self.setup_frame, bg=FELT_DARK)
        bet_row.pack(anchor="w", pady=(14, 4))
        tk.Label(bet_row, text="Your bet per round:", bg=FELT_DARK, fg=TEXT_LIGHT,
                 font=("Helvetica", 12)).pack(side="left")
        self.bet_var = tk.IntVar(value=25)
        tk.Entry(bet_row, textvariable=self.bet_var, width=8,
                 bg="white", fg="black", insertbackground="black").pack(side="left", padx=6)

        tk.Label(bet_row, text="  NPC bet:", bg=FELT_DARK, fg=TEXT_LIGHT,
                 font=("Helvetica", 12)).pack(side="left")
        self.npc_bet_var = tk.IntVar(value=25)
        tk.Entry(bet_row, textvariable=self.npc_bet_var, width=8,
                 bg="white", fg="black", insertbackground="black").pack(side="left", padx=6)

        # Buttons
        btn_row = tk.Frame(self.setup_frame, bg=FELT_DARK)
        btn_row.pack(anchor="w", pady=(16, 4))
        tk.Button(btn_row, text="Start Table", fg="#0a5c2a",
                  font=("Helvetica", 13, "bold"),
                  command=self._start_table).pack(side="left")
        tk.Button(btn_row, text="Cancel", fg=BTN_TEXT,
                  command=self.destroy).pack(side="left", padx=8)

    def _rebuild_seat_rows(self):
        for w in self.rows_frame.winfo_children():
            w.destroy()
        n = int(self.n_seats_var.get())
        self.seat_widgets = []
        default_names = ["Alice", "Bob", "Carol", "Dave", "Erin", "Frank"]
        default_personalities = ["basic", "you", "wreck", "tight", "aggressive", "random"]
        current_you = self.you_var.get()
        for i in range(n):
            row = tk.Frame(self.rows_frame, bg=FELT_DARK)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{i+1}", bg=FELT_DARK, fg=TEXT_LIGHT,
                     width=6, font=("Helvetica", 12)).pack(side="left")

            name_var = tk.StringVar(value=default_names[i])
            tk.Entry(row, textvariable=name_var, width=22,
                     bg="white", fg="black", insertbackground="black").pack(side="left", padx=2)

            pers_var = tk.StringVar(value=default_personalities[i % len(default_personalities)])
            pers_cb = ttk.Combobox(row, textvariable=pers_var, values=PERSONALITIES,
                                   state="readonly", width=22)
            pers_cb.pack(side="left", padx=2)

            desc_var = tk.StringVar(value=PERSONALITY_DESC[pers_var.get()])
            desc_lbl = tk.Label(row, textvariable=desc_var, bg=FELT_DARK, fg=TEXT_LIGHT,
                                width=42, font=("Helvetica", 11), anchor="w")
            desc_lbl.pack(side="left", padx=2)

            def _mk_update(pv=pers_var, dv=desc_var):
                def _cb(_evt=None):
                    dv.set(PERSONALITY_DESC.get(pv.get(), ""))
                return _cb
            pers_cb.bind("<<ComboboxSelected>>", _mk_update())

            you_rb = tk.Radiobutton(row, variable=self.you_var, value=i,
                                    bg=FELT_DARK, activebackground=FELT_DARK,
                                    selectcolor=FELT_DARK)
            you_rb.pack(side="left", padx=6)

            self.seat_widgets.append({"name": name_var, "pers": pers_var, "row": row})
        # Preserve selection if still valid
        if current_you >= n:
            self.you_var.set(0)

    def _start_table(self):
        seats: list[Seat] = []
        you_idx = int(self.you_var.get())
        for i, sw in enumerate(self.seat_widgets):
            name = (sw["name"].get() or f"Seat {i+1}").strip()
            pers = sw["pers"].get() or "basic"
            if i == you_idx:
                pers = "you"  # force user's seat regardless of dropdown
            seats.append(Seat(name=name, personality=pers, bankroll=500))
        if not any(s.is_you for s in seats):
            messagebox.showerror("Pick your seat", "Mark one seat as 'You'.")
            return
        rules = self.rules_getter()
        self.table = Table(rules, seats, self.rng)
        self.you_seat_index = next(i for i, s in enumerate(seats) if s.is_you)
        self._build_play()
        self._show_between_rounds()

    # ---- play screen ----
    def _build_play(self):
        if self.setup_frame:
            self.setup_frame.destroy()
            self.setup_frame = None
        self.play_frame = tk.Frame(self, bg=FELT_DARK)
        self.play_frame.pack(fill="both", expand=True, padx=10, pady=8)

        # Top: rules + buttons
        top = tk.Frame(self.play_frame, bg=FELT_DARK)
        top.pack(fill="x")
        r = self.table.rules
        tk.Label(top, text=f"Table: {r.name}   "
                            f"({r.decks}D · {'H17' if r.dealer_hits_soft_17 else 'S17'} · "
                            f"{'DAS' if r.double_after_split else 'no DAS'} · "
                            f"surr: {r.surrender})",
                 bg=FELT_DARK, fg=TEXT_LIGHT,
                 font=("Helvetica", 12, "bold")).pack(side="left")
        tk.Button(top, text="Setup…", fg=BTN_TEXT,
                  command=self._build_setup).pack(side="right", padx=4)
        tk.Button(top, text="New shoe", fg=BTN_TEXT,
                  command=self._new_shoe).pack(side="right", padx=4)

        # Table canvas — casino felt layout
        self.table_canvas = tk.Canvas(self.play_frame, bg=RAIL, highlightthickness=0)
        self.table_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self._cw_table: dict = {}

        self._dealer_container = tk.Frame(self.table_canvas, bg=FELT)
        tk.Label(self._dealer_container, text="Dealer", bg=FELT, fg=TEXT_LIGHT,
                 font=("Helvetica", 13, "bold")).pack(anchor="w", padx=6)
        self.dealer_cards_frame = tk.Frame(self._dealer_container, bg=FELT)
        self.dealer_cards_frame.pack(padx=6, pady=2, anchor="w")
        self.dealer_total_lbl = tk.Label(self._dealer_container, text="",
                                         bg=FELT, fg=TEXT_LIGHT,
                                         font=("Helvetica", 12))
        self.dealer_total_lbl.pack(anchor="w", padx=6, pady=(0, 2))

        self._seat_frames: list[tk.Frame] = []
        for _ in self.table.seats:
            self._seat_frames.append(tk.Frame(self.table_canvas, bg=FELT))

        self.table_canvas.bind("<Configure>", self._redraw_table)

        # Message
        self.msg_lbl = tk.Label(self.play_frame, text="", bg=FELT_DARK, fg=TEXT_LIGHT,
                                font=("Helvetica", 13, "bold"))
        self.msg_lbl.pack(pady=4)

        # Live table log
        log_frame = tk.LabelFrame(self.play_frame, text="Table log",
                                  bg=FELT_DARK, fg=TEXT_LIGHT,
                                  font=("Helvetica", 11, "bold"))
        log_frame.pack(fill="x", padx=4, pady=(0, 6))
        self.log_text = tk.Text(log_frame, height=6, bg="#111", fg=TEXT_LIGHT,
                                insertbackground=TEXT_LIGHT,
                                font=("Menlo", 11), wrap="word")
        self.log_text.pack(fill="x", padx=6, pady=6)
        self.log_text.tag_config("you", foreground=YOUR_HL, font=("Menlo", 11, "bold"))
        self.log_text.tag_config("moron", foreground=BAD)
        self.log_text.tag_config("good", foreground=GOOD)
        self.log_text.tag_config("dim", foreground="#888")
        self.log_text.tag_config("head", foreground=WARN, font=("Menlo", 11, "bold"))

        # Controls
        ctrl = tk.Frame(self.play_frame, bg=FELT_DARK)
        ctrl.pack(fill="x", pady=(4, 6))

        # Between rounds: Deal button
        self.between_frame = tk.Frame(ctrl, bg=FELT_DARK)
        tk.Label(self.between_frame, text="Your bet:", bg=FELT_DARK, fg=TEXT_LIGHT,
                 font=("Helvetica", 12)).pack(side="left")
        self.bet_play_var = tk.IntVar(value=int(self.bet_var.get()))
        tk.Entry(self.between_frame, textvariable=self.bet_play_var, width=8,
                 bg="white", fg="black", insertbackground="black").pack(side="left", padx=6)
        for amt in (5, 25, 100, 500):
            tk.Button(self.between_frame, text=f"${amt}", fg=BTN_TEXT,
                      command=lambda a=amt: self.bet_play_var.set(a)).pack(side="left", padx=2)
        tk.Button(self.between_frame, text="Deal", fg="#0a5c2a",
                  font=("Helvetica", 13, "bold"),
                  command=self._deal).pack(side="left", padx=10)

        # Your action buttons
        self.action_frame = tk.Frame(ctrl, bg=FELT_DARK)
        self.hit_btn = tk.Button(self.action_frame, text="Hit (H)", width=10, fg=BTN_TEXT,
                                 font=("Helvetica", 12, "bold"),
                                 command=lambda: self._your_action("H"))
        self.stand_btn = tk.Button(self.action_frame, text="Stand (S)", width=10, fg=BTN_TEXT,
                                   font=("Helvetica", 12, "bold"),
                                   command=lambda: self._your_action("S"))
        self.dbl_btn = tk.Button(self.action_frame, text="Double (D)", width=10, fg=BTN_TEXT,
                                 font=("Helvetica", 12, "bold"),
                                 command=lambda: self._your_action("D"))
        self.split_btn = tk.Button(self.action_frame, text="Split (P)", width=10, fg=BTN_TEXT,
                                   font=("Helvetica", 12, "bold"),
                                   command=lambda: self._your_action("P"))
        self.surr_btn = tk.Button(self.action_frame, text="Surrender (R)", width=12, fg=BTN_TEXT,
                                  font=("Helvetica", 12, "bold"),
                                  command=lambda: self._your_action("R"))
        for b in (self.hit_btn, self.stand_btn, self.dbl_btn, self.split_btn, self.surr_btn):
            b.pack(side="left", padx=4)

        # Post-round
        self.next_frame = tk.Frame(ctrl, bg=FELT_DARK)
        tk.Button(self.next_frame, text="Next round", fg="#0a5c2a",
                  font=("Helvetica", 12, "bold"),
                  command=self._show_between_rounds).pack(side="left")

        # Keyboard shortcuts
        self.bind_all("<Key-h>", lambda e: self._kb_action("H"))
        self.bind_all("<Key-s>", lambda e: self._kb_action("S"))
        self.bind_all("<Key-d>", lambda e: self._kb_action("D"))
        self.bind_all("<Key-p>", lambda e: self._kb_action("P"))
        self.bind_all("<Key-r>", lambda e: self._kb_action("R"))

    def _redraw_table(self, event=None):
        c = self.table_canvas
        w, h = c.winfo_width(), c.winfo_height()
        if w < 100 or h < 100:
            return
        c.delete("felt")

        cx = w / 2
        pad = 10
        rx = (w - 2 * pad) / 2
        curve_depth = h * 0.30
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

        r = self.table.rules
        payout = "3 TO 2" if r.blackjack_payout >= 1.5 else "6 TO 5"
        c.create_text(cx, h * 0.26,
                      text=f"BLACKJACK PAYS {payout}",
                      fill=GOLD, font=("Helvetica", 13, "bold italic"), tags="felt")
        dealer_txt = ("DEALER HITS SOFT 17" if r.dealer_hits_soft_17
                      else "DEALER STANDS ON ALL 17s")
        c.create_text(cx, h * 0.32, text=dealer_txt,
                      fill=GOLD, font=("Helvetica", 10), tags="felt")

        ins_y = h * 0.39
        ins_rx = rx * 0.55
        ins_pts = []
        for i in range(51):
            a = math.pi * i / 50
            ins_pts.extend([cx + ins_rx * math.cos(a),
                            ins_y + curve_depth * 0.08 * math.sin(a)])
        c.create_line(ins_pts, fill=GOLD, width=1.5, dash=(6, 3),
                      smooth=True, tags="felt")
        c.create_text(cx, ins_y - 6,
                      text="INSURANCE PAYS 2 TO 1",
                      fill=GOLD, font=("Helvetica", 8), tags="felt")

        n = len(self.table.seats)
        usable_w = w - 2 * pad - 40
        for i in range(n):
            frac = (i + 0.5) / n
            bx = pad + 20 + usable_w * frac
            by = h * 0.47 + h * 0.03 * math.sin(math.pi * frac)
            cr = 14
            c.create_oval(bx - cr, by - cr, bx + cr, by + cr,
                          outline=GOLD, width=2, tags="felt")

        if "dealer" not in self._cw_table:
            self._cw_table["dealer"] = c.create_window(
                cx, h * 0.06, window=self._dealer_container, anchor="n")
        else:
            c.coords(self._cw_table["dealer"], cx, h * 0.06)

        for i, sf in enumerate(self._seat_frames):
            frac = (i + 0.5) / n
            sx = pad + 20 + usable_w * frac
            sy = h * 0.47 + h * 0.03 * math.sin(math.pi * frac) + 20
            key = f"seat_{i}"
            if key not in self._cw_table:
                self._cw_table[key] = c.create_window(
                    sx, sy, window=sf, anchor="n")
            else:
                c.coords(self._cw_table[key], sx, sy)

    # ---- state helpers ----
    def _kb_action(self, code):
        # Only act if the action frame is currently visible
        if self.action_frame.winfo_ismapped() and self._is_your_turn():
            self._your_action(code)

    def _show_between_rounds(self):
        self.between_rounds = True
        self.msg_lbl.config(text="Place your bet and click Deal.")
        for f in (self.action_frame, self.next_frame):
            f.pack_forget()
        self.between_frame.pack(side="left")
        # Reset display: hide previous round
        self._clear(self.dealer_cards_frame)
        self.dealer_total_lbl.config(text="")
        self._render_seats(reset=True)

    def _show_playing(self):
        self.between_rounds = False
        for f in (self.between_frame, self.next_frame):
            f.pack_forget()
        self.action_frame.pack(side="left")

    def _show_finished(self):
        for f in (self.between_frame, self.action_frame):
            f.pack_forget()
        self.next_frame.pack(side="left")

    def _clear(self, frame):
        for w in frame.winfo_children():
            w.destroy()

    def _new_shoe(self):
        if not self.table:
            return
        self.table.new_shoe()
        messagebox.showinfo("New shoe", "Fresh shoe shuffled.")

    # ---- deal / play ----
    def _deal(self):
        try:
            bet = int(self.bet_play_var.get())
        except Exception:
            messagebox.showerror("Invalid bet", "Enter a whole-number bet.")
            return
        npc_bet = int(self.npc_bet_var.get()) if self.npc_bet_var.get() else 25
        you_seat = self.table.seats[self.you_seat_index]
        if bet <= 0 or bet > you_seat.bankroll:
            messagebox.showerror("Bet problem",
                                 f"Bet must be 1..{you_seat.bankroll}.")
            return
        # Assemble bets per seat
        bets = []
        for i, s in enumerate(self.table.seats):
            if s.is_you:
                bets.append(bet)
            else:
                bets.append(min(npc_bet, s.bankroll))
        self.table.start_round(bets)
        self._render_all(hide_dealer=True)
        self._show_playing()
        self.msg_lbl.config(text="")

        # Fresh log for this round
        self.log_text.delete("1.0", "end")
        up = str(self.table.dealer_upcard())
        self.log_text.insert("end", f"--- New round · dealer shows {up} ---\n", "head")
        self._advance_or_prompt()

    def _advance_or_prompt(self):
        """If it's an NPC's turn, schedule an NPC action. Otherwise show buttons."""
        if self.table.all_players_done():
            self._resolve()
            return
        seat = self.table.current_seat()
        if seat is None:
            self._resolve()
            return
        if seat.is_you:
            self._update_action_availability()
            self.msg_lbl.config(text=f"Your turn — {seat.name}. Pick an action.")
            return
        # NPC's turn: schedule an action after a short delay
        self.msg_lbl.config(text=f"{seat.name} ({seat.personality}) is thinking…")
        self._render_all(hide_dealer=True)
        self.after(650, self._npc_step)

    def _npc_step(self):
        if self.table is None or self.table.all_players_done():
            self._resolve(); return
        seat = self.table.current_seat()
        if seat is None or seat.is_you:
            self._advance_or_prompt(); return
        # Snapshot before the action for the log
        hand_before = seat.active_hand()
        cards_before = " ".join(str(c) for c in hand_before.cards) if hand_before else ""
        total_before = hand_before.best() if hand_before else 0
        up_rank = self.table.dealer_upcard().rank
        try:
            act = npc_action(seat, up_rank, self.table.rules, self.rng)
            legal, drawn = self.table.apply_action(act)
            if not legal:
                legal, drawn = self.table.apply_action("S")
                act = "S"
        except Exception:
            legal, drawn = self.table.apply_action("S")
            act = "S"
        self._log_action(seat, act, cards_before, total_before, up_rank, drawn)
        self._render_all(hide_dealer=True)
        # Continue: another NPC, you, or resolve
        if self.table.all_players_done():
            self._resolve()
        else:
            self.after(500, self._advance_or_prompt)

    def _your_action(self, act: str):
        seat = self.table.current_seat()
        if not seat or not seat.is_you:
            return
        hand_before = seat.active_hand()
        cards_before = " ".join(str(c) for c in hand_before.cards) if hand_before else ""
        total_before = hand_before.best() if hand_before else 0
        up_rank = self.table.dealer_upcard().rank
        legal, drawn = self.table.apply_action(act)
        if not legal:
            messagebox.showinfo("Not allowed", "That action isn't legal here.")
            return
        self._log_action(seat, act, cards_before, total_before, up_rank, drawn)
        self._render_all(hide_dealer=True)
        if self.table.all_players_done():
            self._resolve()
        else:
            self._advance_or_prompt()

    def _log_action(self, seat, act, cards_before, total_before, up_rank, drawn):
        act_name = {"H":"Hit", "S":"Stand", "D":"Double", "P":"Split", "R":"Surrender"}.get(act, act)
        tag = "you" if seat.is_you else ("moron" if seat.personality == "moron" else "dim")
        line = f"{seat.name} ({seat.personality}): {act_name}  hand [{cards_before}] ({total_before}) vs {up_rank}"
        if drawn:
            line += f" → drew {drawn}"
        line += "\n"
        self.log_text.insert("end", line, tag)
        self.log_text.see("end")

    def _resolve(self):
        # Log dealer's play
        dealer_before = " ".join(str(c) for c in self.table.dealer_hand.cards)
        cards_pre_len = len(self.table.dealer_hand.cards)
        self.table.dealer_play()
        drawn_by_dealer = [str(c) for c in self.table.dealer_hand.cards[cards_pre_len:]]
        results = self.table.settle()
        self._render_all(hide_dealer=False)

        if drawn_by_dealer:
            self.log_text.insert("end",
                f"Dealer plays: [{dealer_before}] → drew {' '.join(drawn_by_dealer)} → "
                f"{self.table.dealer_hand.best()}\n", "head")
        else:
            self.log_text.insert("end",
                f"Dealer stands: {self.table.dealer_hand.best()}\n", "head")

        # Show settlement per seat
        parts = []
        your_net = 0
        for i, (s, res) in enumerate(zip(self.table.seats, results)):
            if not res:
                parts.append(f"{s.name}: sat out")
                continue
            net = sum(p for _, p, _ in res)
            outcomes = ", ".join(o for _, _, o in res)
            tag = "*YOU* " if s.is_you else ""
            parts.append(f"{tag}{s.name}: {outcomes} ({'+' if net>=0 else ''}{net})")
            if s.is_you:
                your_net = net
            log_tag = "you" if s.is_you else ("good" if net > 0 else ("moron" if net < 0 else "dim"))
            self.log_text.insert("end",
                f"  {s.name}: {outcomes}  net {'+' if net>=0 else ''}${net}   (bank ${s.bankroll})\n",
                log_tag)
        self.log_text.see("end")
        self.msg_lbl.config(text="  ·  ".join(parts))

        # Play a sound for YOUR outcome
        if any(o == "blackjack" for _, _, o in results[self.you_seat_index]):
            sounds.play("bj")
        elif your_net > 0:
            sounds.play("win")
        elif your_net < 0:
            sounds.play("lose")
        else:
            sounds.play("push")

        self._show_finished()

    def _is_your_turn(self) -> bool:
        if not self.table or self.between_rounds:
            return False
        seat = self.table.current_seat()
        return bool(seat and seat.is_you)

    def _update_action_availability(self):
        seat = self.table.current_seat()
        if not seat:
            return
        hand = seat.active_hand()
        if not hand:
            return
        rules = self.table.rules
        self.hit_btn.config(state="normal")
        self.stand_btn.config(state="normal")
        self.dbl_btn.config(state="normal" if hand.can_double(rules) and seat.bankroll >= hand.bet else "disabled")
        self.split_btn.config(state="normal" if hand.can_split(rules, len(seat.hands)) and seat.bankroll >= hand.bet else "disabled")
        self.surr_btn.config(state="normal" if hand.can_surrender(rules) else "disabled")

    # ---- rendering ----
    def _render_all(self, hide_dealer: bool):
        self._render_dealer(hide_dealer=hide_dealer)
        self._render_seats()

    def _render_dealer(self, hide_dealer: bool):
        self._clear(self.dealer_cards_frame)
        for i, c in enumerate(self.table.dealer_hand.cards):
            hidden = (hide_dealer and i == 0)
            _card_widget(self.dealer_cards_frame, c, hidden=hidden).pack(side="left")
        if not hide_dealer and self.table.dealer_hand.cards:
            total, soft = self.table.dealer_hand.totals()
            txt = f"Total: {total}{' (soft)' if soft else ''}"
            if self.table.dealer_hand.is_blackjack():
                txt = "BLACKJACK"
            self.dealer_total_lbl.config(text=txt)
        else:
            self.dealer_total_lbl.config(text="Total: ?")

    def _render_seats(self, reset: bool = False):
        if not self.table:
            return
        for i, (sf, s) in enumerate(zip(self._seat_frames, self.table.seats)):
            for w in sf.winfo_children():
                w.destroy()

            active = (self.table.in_round
                      and not self.table.all_players_done()
                      and self.table.current_seat_index == i)
            border_color = YOUR_HL if s.is_you else WARN
            sf.config(highlightthickness=3 if active else 0,
                      highlightbackground=border_color)

            title = f"{'★ ' if s.is_you else ''}{s.name}"
            tk.Label(sf, text=title, bg=FELT,
                     fg=(YOUR_HL if s.is_you else TEXT_LIGHT),
                     font=("Helvetica", 11, "bold")).pack(anchor="w")
            tk.Label(sf, text=f"({s.personality})   ${s.bankroll}",
                     bg=FELT, fg=TEXT_LIGHT,
                     font=("Helvetica", 10)).pack(anchor="w", pady=(0, 2))

            if reset or not s.hands:
                tk.Label(sf, text="(no hand)", bg=FELT, fg=TEXT_LIGHT,
                         font=("Helvetica", 10)).pack(anchor="w")
                continue

            for hi, h in enumerate(s.hands):
                hf = tk.Frame(sf, bg=FELT)
                hf.pack(anchor="w", pady=2)
                cards_row = tk.Frame(hf, bg=FELT)
                cards_row.pack(anchor="w")
                for c in h.cards:
                    _card_widget(cards_row, c).pack(side="left")
                total, soft = h.totals()
                if h.cards:
                    tag = f"{total}{' soft' if soft else ''}"
                    if h.is_blackjack():
                        tag = "BJ!"
                    if h.busted:
                        tag = "BUST"
                    if h.surrendered:
                        tag = "SURR"
                    tk.Label(hf, text=f"  {tag}   bet ${h.bet}",
                             bg=FELT, fg=TEXT_LIGHT,
                             font=("Helvetica", 10)).pack(anchor="w")
