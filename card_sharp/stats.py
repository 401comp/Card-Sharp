import tkinter as tk
from tkinter import ttk
from . import db, overrides
from .strategy import ACTION_NAMES


FELT_DARK = "#083f22"
TEXT_LIGHT = "#f2f2f2"
WARN = "#ffb74d"
GOOD = "#4caf50"
BAD = "#e53935"


def center(win, w, h):
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//3}")


class StatsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Card-Sharp — Stats")
        self.configure(bg=FELT_DARK)
        self.transient(parent)

        top = tk.Frame(self, bg=FELT_DARK)
        top.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(top, text="Stats", bg=FELT_DARK, fg=TEXT_LIGHT,
                 font=("Helvetica", 16, "bold")).pack(side="left")
        tk.Button(top, text="Refresh", fg="#111",
                  command=self._refresh).pack(side="right")

        # Overview strip
        self.overview = tk.Label(self, text="", bg=FELT_DARK, fg=WARN,
                                 font=("Menlo", 13), justify="left")
        self.overview.pack(fill="x", padx=14, pady=(6, 4), anchor="w")

        # Notebook: By drill | By category | Top mistakes | Recent sessions
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=8)

        # Common styling for text boxes
        def new_text(parent):
            t = tk.Text(parent, bg="#111", fg=TEXT_LIGHT,
                        insertbackground=TEXT_LIGHT,
                        font=("Menlo", 12), wrap="none")
            t.pack(fill="both", expand=True, padx=6, pady=6)
            t.tag_config("head", foreground=WARN, font=("Menlo", 12, "bold"))
            t.tag_config("good", foreground=GOOD)
            t.tag_config("bad", foreground=BAD)
            return t

        f1 = tk.Frame(nb, bg=FELT_DARK); nb.add(f1, text="By drill")
        self.t_drill = new_text(f1)

        f2 = tk.Frame(nb, bg=FELT_DARK); nb.add(f2, text="By category")
        self.t_cat = new_text(f2)

        f3 = tk.Frame(nb, bg=FELT_DARK); nb.add(f3, text="Top mistakes")
        self.t_mistakes = new_text(f3)

        f4 = tk.Frame(nb, bg=FELT_DARK); nb.add(f4, text="Recent sessions")
        self.t_sessions = new_text(f4)

        f5 = tk.Frame(nb, bg=FELT_DARK); nb.add(f5, text="Your deviations")
        self.t_devs = new_text(f5)

        center(self, 780, 560)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._refresh()

    def _refresh(self):
        # Overview
        o = db.stats_overview()
        self.overview.config(text=(
            f"Overall:  {o['total_correct']}/{o['total_decisions']} correct  "
            f"({o['overall_accuracy']:.1f}%)"
            f"        Sim play: {o['play_correct']}/{o['play_decisions']}     "
            f"Drills: {o['drill_correct']}/{o['drill_attempts']}"
        ))

        # By drill
        self.t_drill.delete("1.0", "end")
        self.t_drill.insert("end",
            f"{'Drill':<14}{'Attempts':>10}{'Correct':>10}{'Accuracy':>12}\n", "head")
        for r in db.stats_by_drill():
            line = f"{r['drill']:<14}{r['attempts']:>10}{r['correct']:>10}{r['accuracy']:>11.1f}%\n"
            tag = "good" if r["accuracy"] >= 80 else ("bad" if r["accuracy"] < 60 else "")
            self.t_drill.insert("end", line, tag)
        if not db.stats_by_drill():
            self.t_drill.insert("end", "(no drill attempts yet — open the Trainer)\n")

        # By category
        self.t_cat.delete("1.0", "end")
        self.t_cat.insert("end",
            f"{'Category':<14}{'Attempts':>10}{'Correct':>10}{'Accuracy':>12}\n", "head")
        for r in db.stats_by_category():
            line = f"{r['category']:<14}{r['attempts']:>10}{r['correct']:>10}{r['accuracy']:>11.1f}%\n"
            tag = "good" if r["accuracy"] >= 80 else ("bad" if r["accuracy"] < 60 else "")
            self.t_cat.insert("end", line, tag)
        if not db.stats_by_category():
            self.t_cat.insert("end", "(no attempts yet)\n")

        # Top mistakes
        self.t_mistakes.delete("1.0", "end")
        self.t_mistakes.insert("end",
            f"{'Your hand':<20}{'Up':<5}{'You':<12}{'Best':<12}{'Times wrong':>12}\n", "head")
        for r in db.top_mistakes(20):
            you = ACTION_NAMES.get(r["player_action"], r["player_action"])
            best = ACTION_NAMES.get(r["correct_action"], r["correct_action"])
            self.t_mistakes.insert("end",
                f"{r['player_cards']:<20}{r['dealer_up']:<5}{you:<12}{best:<12}{r['count']:>12}\n",
                "bad")
        if not db.top_mistakes(1):
            self.t_mistakes.insert("end", "(no mistakes recorded — brag away)\n", "good")

        # Recent sessions
        self.t_sessions.delete("1.0", "end")
        self.t_sessions.insert("end",
            f"{'When':<20}{'Preset':<28}{'Hands':>7}{'Acc%':>7}{'Δ$':>8}\n", "head")
        for r in db.recent_sessions(20):
            delta = "" if r["delta"] is None else f"{r['delta']:+d}"
            line = (f"{r['started_at']:<20}"
                    f"{(r['preset'] or '')[:26]:<28}"
                    f"{r['hands']:>7}"
                    f"{r['accuracy']:>7.1f}"
                    f"{delta:>8}\n")
            tag = ""
            if r["delta"] is not None:
                tag = "good" if r["delta"] > 0 else ("bad" if r["delta"] < 0 else "")
            self.t_sessions.insert("end", line, tag)
        if not db.recent_sessions(1):
            self.t_sessions.insert("end", "(no sessions yet)\n")

        # Your deviations — usage + outcomes
        self.t_devs.delete("1.0", "end")
        rows = db.deviation_stats()
        self.t_devs.insert("end",
            f"{'Hand':<22}{'Up':<5}{'Play':<10}{'BS':<10}"
            f"{'Uses':>6}{'W':>4}{'L':>4}{'P':>4}{'Net$':>9}{'Avg$/hand':>11}\n",
            "head")
        if not rows:
            self.t_devs.insert("end",
                "(no deviations used yet — set some in Deviations… and play a hand)\n")
        for r in rows:
            hand_txt = overrides.describe_hand_key(r["hand_key"])
            up_txt = "10" if r["upcard"] == "T" else r["upcard"]
            play = ACTION_NAMES.get(r["chosen_action"], r["chosen_action"])
            bs = ACTION_NAMES.get(r["bs_action"], r["bs_action"])
            net = r["net"]
            avg = r["avg"]
            tag = "good" if net > 0 else ("bad" if net < 0 else "")
            self.t_devs.insert("end",
                f"{hand_txt[:20]:<22}{up_txt:<5}{play:<10}{bs:<10}"
                f"{r['uses']:>6}{r['wins']:>4}{r['losses']:>4}{r['pushes']:>4}"
                f"{net:>+9d}{avg:>+11.2f}\n",
                tag)
