import tkinter as tk
from tkinter import ttk, messagebox
from .rules import Rules, PRESETS


def center(win, w, h):
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//3}")


class RulesEditor(tk.Toplevel):
    """Dialog to pick a preset, edit rules, save as custom."""

    def __init__(self, parent, current: Rules, custom_presets: dict):
        super().__init__(parent)
        self.title("Rules")
        self.configure(bg="#222")
        self.transient(parent)
        self.grab_set()
        self.result = None  # (Rules, custom_presets_dict, chosen_name)

        self.custom = dict(custom_presets)
        self.current = current

        # Build preset list = built-in + custom
        self.preset_names = list(PRESETS.keys()) + list(self.custom.keys())

        pad = {"padx": 8, "pady": 4}
        row = 0

        tk.Label(self, text="Preset:", bg="#222", fg="white",
                 font=("Helvetica", 12, "bold")).grid(row=row, column=0, sticky="e", **pad)
        self.preset_var = tk.StringVar(value=current.name if current.name in self.preset_names else self.preset_names[0])
        self.preset_menu = ttk.Combobox(self, textvariable=self.preset_var, values=self.preset_names,
                                        state="readonly", width=32)
        self.preset_menu.grid(row=row, column=1, sticky="w", **pad)
        self.preset_menu.bind("<<ComboboxSelected>>", self._on_preset_change)
        row += 1

        # Numeric / choice fields
        self.decks_var = tk.IntVar()
        self.h17_var = tk.BooleanVar()
        self.bj_var = tk.StringVar()   # "3:2" or "6:5"
        self.das_var = tk.BooleanVar()
        self.double_var = tk.StringVar()   # any2 / 9_10_11 / 10_11
        self.split_max_var = tk.IntVar()
        self.resplit_a_var = tk.BooleanVar()
        self.hit_split_a_var = tk.BooleanVar()
        self.surr_var = tk.StringVar()     # none / late / early
        self.pen_var = tk.DoubleVar()

        def field(label, widget, r):
            tk.Label(self, text=label, bg="#222", fg="white",
                     font=("Helvetica", 12)).grid(row=r, column=0, sticky="e", **pad)
            widget.grid(row=r, column=1, sticky="w", **pad)

        field("Decks:", ttk.Combobox(self, textvariable=self.decks_var, values=[1, 2, 4, 6, 8],
                                     state="readonly", width=10), row); row += 1
        field("Dealer soft 17:", ttk.Combobox(self, textvariable=self._proxy_bool(self.h17_var, "Hits (H17)", "Stands (S17)"),
                                              values=["Stands (S17)", "Hits (H17)"], state="readonly", width=18), row); row += 1
        field("Blackjack payout:", ttk.Combobox(self, textvariable=self.bj_var,
                                                values=["3:2", "6:5"], state="readonly", width=10), row); row += 1
        field("Double after split:", ttk.Combobox(self, textvariable=self._proxy_bool(self.das_var, "Yes", "No"),
                                                  values=["Yes", "No"], state="readonly", width=10), row); row += 1
        field("Double allowed on:", ttk.Combobox(self, textvariable=self.double_var,
                                                 values=["any two cards", "9/10/11 only", "10/11 only"],
                                                 state="readonly", width=18), row); row += 1
        field("Max split hands:", ttk.Combobox(self, textvariable=self.split_max_var,
                                               values=[2, 3, 4], state="readonly", width=10), row); row += 1
        field("Resplit aces:", ttk.Combobox(self, textvariable=self._proxy_bool(self.resplit_a_var, "Yes", "No"),
                                            values=["Yes", "No"], state="readonly", width=10), row); row += 1
        field("Hit split aces:", ttk.Combobox(self, textvariable=self._proxy_bool(self.hit_split_a_var, "Yes", "No"),
                                              values=["Yes", "No"], state="readonly", width=10), row); row += 1
        field("Surrender:", ttk.Combobox(self, textvariable=self.surr_var,
                                         values=["none", "late", "early"], state="readonly", width=10), row); row += 1
        field("Penetration (0.5-0.95):", tk.Entry(self, textvariable=self.pen_var, width=10,
                                                  bg="white", fg="black", insertbackground="black"), row); row += 1

        # Notes
        tk.Label(self, text="Notes:", bg="#222", fg="white",
                 font=("Helvetica", 12)).grid(row=row, column=0, sticky="ne", **pad)
        self.notes_text = tk.Text(self, height=3, width=48, bg="white", fg="black",
                                  insertbackground="black", font=("Helvetica", 11), wrap="word")
        self.notes_text.grid(row=row, column=1, sticky="w", **pad); row += 1

        # Save-as name
        tk.Label(self, text="Save as (optional name):", bg="#222", fg="white",
                 font=("Helvetica", 12)).grid(row=row, column=0, sticky="e", **pad)
        self.save_as_var = tk.StringVar()
        tk.Entry(self, textvariable=self.save_as_var, width=32,
                 bg="white", fg="black", insertbackground="black").grid(row=row, column=1, sticky="w", **pad)
        row += 1

        # Buttons
        btns = tk.Frame(self, bg="#222")
        btns.grid(row=row, column=0, columnspan=2, pady=10)
        ttk.Button(btns, text="Apply", command=self._apply).pack(side="left", padx=6)
        ttk.Button(btns, text="Save as new preset", command=self._save_new).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancel", command=self._cancel).pack(side="left", padx=6)

        # Load values
        self._load_rules(current)
        center(self, 560, 500)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    # Combobox needs StringVar; we shim bool <-> label
    def _proxy_bool(self, boolvar: tk.BooleanVar, yes_label: str, no_label: str) -> tk.StringVar:
        sv = tk.StringVar()

        def to_str(*_):
            sv.set(yes_label if boolvar.get() else no_label)

        def to_bool(*_):
            boolvar.set(sv.get() == yes_label)

        boolvar.trace_add("write", to_str)
        sv.trace_add("write", to_bool)
        to_str()
        return sv

    def _load_rules(self, r: Rules):
        self.decks_var.set(r.decks)
        self.h17_var.set(r.dealer_hits_soft_17)
        self.bj_var.set("3:2" if abs(r.blackjack_payout - 1.5) < 0.01 else "6:5")
        self.das_var.set(r.double_after_split)
        self.double_var.set({"any2": "any two cards", "9_10_11": "9/10/11 only", "10_11": "10/11 only"}[r.double_on])
        self.split_max_var.set(r.split_max_hands)
        self.resplit_a_var.set(r.resplit_aces)
        self.hit_split_a_var.set(r.hit_split_aces)
        self.surr_var.set(r.surrender)
        self.pen_var.set(r.penetration)
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", r.notes)
        self.save_as_var.set("")

    def _on_preset_change(self, _evt=None):
        name = self.preset_var.get()
        if name in PRESETS:
            self._load_rules(PRESETS[name])
        elif name in self.custom:
            self._load_rules(Rules.from_dict(self.custom[name]))

    def _read_rules(self) -> Rules:
        double_map = {"any two cards": "any2", "9/10/11 only": "9_10_11", "10/11 only": "10_11"}
        try:
            pen = float(self.pen_var.get())
        except Exception:
            pen = 0.75
        pen = max(0.5, min(0.95, pen))
        return Rules(
            name=self.preset_var.get(),
            decks=int(self.decks_var.get()),
            dealer_hits_soft_17=bool(self.h17_var.get()),
            blackjack_payout=1.5 if self.bj_var.get() == "3:2" else 1.2,
            double_on=double_map[self.double_var.get()],
            double_after_split=bool(self.das_var.get()),
            split_max_hands=int(self.split_max_var.get()),
            resplit_aces=bool(self.resplit_a_var.get()),
            hit_split_aces=bool(self.hit_split_a_var.get()),
            surrender=self.surr_var.get(),
            penetration=pen,
            notes=self.notes_text.get("1.0", "end").strip(),
        )

    def _apply(self):
        r = self._read_rules()
        # If they edited a built-in preset without saving, apply for this session only,
        # keep the name as-is (built-ins won't be overwritten in prefs).
        # If name matches a custom preset, update it.
        if r.name in self.custom:
            self.custom[r.name] = r.to_dict()
        self.result = (r, self.custom, r.name)
        self.destroy()

    def _save_new(self):
        name = self.save_as_var.get().strip()
        if not name:
            messagebox.showerror("Name required", "Enter a name in 'Save as' before saving.")
            return
        if name in PRESETS:
            messagebox.showerror("Reserved name", "That name is a built-in preset. Choose another.")
            return
        r = self._read_rules()
        r.name = name
        self.custom[name] = r.to_dict()
        # add to combobox list
        vals = list(self.preset_menu.cget("values")) + [name]
        self.preset_menu.config(values=vals)
        self.preset_var.set(name)
        messagebox.showinfo("Saved", f"Custom preset '{name}' saved.")

    def _cancel(self):
        self.result = None
        self.destroy()
