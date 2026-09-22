import tkinter as tk
from tkinter import ttk, messagebox
from . import overrides
from .strategy import ACTION_NAMES


FELT_DARK = "#083f22"
TEXT_LIGHT = "#f2f2f2"
WARN = "#ffb74d"


def center(win, w, h):
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//3}")


HAND_TYPES = ["Hard total", "Soft total", "Pair"]
UPCARD_LABELS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "A"]
UPCARD_TO_KEY = {"10": "T", "A": "A", **{s: s for s in "23456789"}}


class DeviationsEditor(tk.Toplevel):
    """Add / remove personal strategy deviations."""

    def __init__(self, parent, deviations: dict, on_save):
        super().__init__(parent)
        self.title("Personal deviations")
        self.configure(bg=FELT_DARK)
        self.transient(parent)
        self.grab_set()
        self.deviations = dict(deviations)
        self.on_save = on_save

        header = tk.Label(self, text="Your personal deviations from basic strategy",
                          bg=FELT_DARK, fg=WARN, font=("Helvetica", 14, "bold"))
        header.pack(padx=12, pady=(10, 4))
        sub = tk.Label(self,
                       text="If a deviation isn't legal in a given hand (e.g. you already hit and\n"
                            "can't double), the game falls back to basic strategy for that decision.",
                       bg=FELT_DARK, fg=TEXT_LIGHT,
                       font=("Helvetica", 11), justify="center")
        sub.pack(padx=12, pady=(0, 8))

        # --- Add-row area ---
        add_frame = tk.LabelFrame(self, text="Add / update deviation",
                                  bg=FELT_DARK, fg=TEXT_LIGHT,
                                  font=("Helvetica", 12, "bold"))
        add_frame.pack(fill="x", padx=12, pady=6)

        row = tk.Frame(add_frame, bg=FELT_DARK)
        row.pack(padx=8, pady=8, fill="x")

        # Hand type
        tk.Label(row, text="Hand:", bg=FELT_DARK, fg=TEXT_LIGHT,
                 font=("Helvetica", 12)).pack(side="left")
        self.type_var = tk.StringVar(value="Hard total")
        type_cb = ttk.Combobox(row, textvariable=self.type_var, values=HAND_TYPES,
                               state="readonly", width=12)
        type_cb.pack(side="left", padx=6)
        type_cb.bind("<<ComboboxSelected>>", self._on_type_change)

        # Hand value
        self.hand_var = tk.StringVar()
        self.hand_cb = ttk.Combobox(row, textvariable=self.hand_var, values=[],
                                    state="readonly", width=22)
        self.hand_cb.pack(side="left", padx=6)

        # Upcard
        tk.Label(row, text="vs Up:", bg=FELT_DARK, fg=TEXT_LIGHT,
                 font=("Helvetica", 12)).pack(side="left", padx=(10, 2))
        self.up_var = tk.StringVar(value="5")
        up_cb = ttk.Combobox(row, textvariable=self.up_var, values=UPCARD_LABELS,
                             state="readonly", width=4)
        up_cb.pack(side="left", padx=4)

        # Action
        tk.Label(row, text="→ Play:", bg=FELT_DARK, fg=TEXT_LIGHT,
                 font=("Helvetica", 12)).pack(side="left", padx=(10, 2))
        self.action_var = tk.StringVar(value="Double")
        act_cb = ttk.Combobox(row, textvariable=self.action_var,
                              values=list(ACTION_NAMES.values()),
                              state="readonly", width=12)
        act_cb.pack(side="left", padx=4)

        # Save / remove
        btns = tk.Frame(add_frame, bg=FELT_DARK)
        btns.pack(padx=8, pady=(0, 8), fill="x")
        tk.Button(btns, text="Save deviation", fg="#0a5c2a",
                  font=("Helvetica", 12, "bold"),
                  command=self._add).pack(side="left")
        tk.Button(btns, text="Remove this hand+up", fg="#111",
                  command=self._remove_this).pack(side="left", padx=8)

        # --- Current list ---
        list_frame = tk.LabelFrame(self, text="Current deviations",
                                   bg=FELT_DARK, fg=TEXT_LIGHT,
                                   font=("Helvetica", 12, "bold"))
        list_frame.pack(fill="both", expand=True, padx=12, pady=8)

        cols = ("hand", "up", "action")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=10)
        self.tree.heading("hand", text="Hand")
        self.tree.heading("up", text="vs Upcard")
        self.tree.heading("action", text="Action")
        self.tree.column("hand", width=220)
        self.tree.column("up", width=100, anchor="center")
        self.tree.column("action", width=120, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

        list_btns = tk.Frame(list_frame, bg=FELT_DARK)
        list_btns.pack(fill="x", padx=6, pady=(0, 6))
        tk.Button(list_btns, text="Delete selected", fg="#111",
                  command=self._delete_selected).pack(side="left")
        tk.Button(list_btns, text="Clear all", fg="#b00020",
                  command=self._clear_all).pack(side="left", padx=8)

        # --- Bottom action bar ---
        bar = tk.Frame(self, bg=FELT_DARK)
        bar.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(bar, text="Save & Close", fg="#0a5c2a",
                  font=("Helvetica", 12, "bold"),
                  command=self._save_and_close).pack(side="right")
        tk.Button(bar, text="Cancel", fg="#111",
                  command=self._cancel).pack(side="right", padx=8)

        self._on_type_change()
        self._refresh_list()
        center(self, 720, 560)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    # ---- hand-value dropdown fill ----
    def _on_type_change(self, _evt=None):
        t = self.type_var.get()
        if t == "Hard total":
            vals = [f"{n}" for n in range(5, 21)]
            self.hand_var.set("8")
        elif t == "Soft total":
            vals = [f"{n} (A,{n-11})" for n in range(13, 21)]   # A,2..A,9
            self.hand_var.set(vals[0])
        else:  # Pair
            vals = ["2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s", "10s", "As"]
            self.hand_var.set("8s")
        self.hand_cb.config(values=vals)

    def _current_hand_key(self) -> str:
        t = self.type_var.get()
        v = self.hand_var.get().strip()
        if t == "Hard total":
            return f"hard_{int(v)}"
        if t == "Soft total":
            n = int(v.split(" ")[0])
            return f"soft_{n}"
        # Pair
        if v.startswith("As"):
            return "pair_A"
        if v.startswith("10s"):
            return "pair_T"
        return f"pair_{int(v.rstrip('s'))}"

    def _current_upcard(self) -> str:
        return UPCARD_TO_KEY[self.up_var.get()]

    def _current_action_code(self) -> str:
        name = self.action_var.get()
        for code, n in ACTION_NAMES.items():
            if n == name:
                return code
        return "H"

    # ---- actions ----
    def _add(self):
        try:
            hk = self._current_hand_key()
        except Exception:
            messagebox.showerror("Bad selection", "Pick a hand value.")
            return
        up = self._current_upcard()
        act = self._current_action_code()
        overrides.set_(self.deviations, hk, up, act)
        self._refresh_list()

    def _remove_this(self):
        try:
            hk = self._current_hand_key()
        except Exception:
            return
        up = self._current_upcard()
        overrides.remove(self.deviations, hk, up)
        self._refresh_list()

    def _delete_selected(self):
        for item in self.tree.selection():
            hk, up, _ = self.tree.item(item, "values")
            # Convert user-facing "10"/"A" back to key form
            up_key = UPCARD_TO_KEY.get(up, up)
            # Convert display hand text back to key by looking up items map
            key = self._display_to_key.get(item)
            if key:
                self.deviations.pop(key, None)
        self._refresh_list()

    def _clear_all(self):
        if messagebox.askyesno("Clear all", "Delete every deviation?"):
            self.deviations.clear()
            self._refresh_list()

    def _refresh_list(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        self._display_to_key: dict[str, str] = {}
        for hk, up, act in overrides.list_all(self.deviations):
            hand_txt = overrides.describe_hand_key(hk)
            up_txt = "10" if up == "T" else up
            act_txt = ACTION_NAMES.get(act, act)
            item_id = self.tree.insert("", "end", values=(hand_txt, up_txt, act_txt))
            self._display_to_key[item_id] = f"{hk}|{up}"

    def _save_and_close(self):
        self.on_save(self.deviations)
        self.destroy()

    def _cancel(self):
        self.destroy()
