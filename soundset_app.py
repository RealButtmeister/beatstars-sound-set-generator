"""A local, snapshot-based sound-set browser and export window."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import webbrowser

from generator import BASE, export_collection, load_palettes, load_rows, select_sets


SCOPE_LABELS = {
    "All chart samples": "all",
    "Recent releases": "recent_releases",
    "All time": "all_time",
}


class SoundSetApp:
    def __init__(self, root):
        self.root = root
        self.rows = []
        self.palettes = []
        self.active = []
        self.unmatched = []
        self.source_path = BASE / "observations.csv"
        self.observed_at = tk.StringVar(value=date.today().isoformat())
        self.source_name = tk.StringVar(value=self.source_path.name)
        self.scope_label = tk.StringVar(value="All chart samples")
        self.search = tk.StringVar()
        self.summary = tk.StringVar(value="Choose your observations CSV to begin.")
        self.status = tk.StringVar(value="")
        self._build_window()
        self.search.trace_add("write", lambda *_: self._filter_list())
        self.root.after_idle(self._load_initial)

    @property
    def scope(self):
        return SCOPE_LABELS[self.scope_label.get()]

    def _build_window(self):
        root = self.root
        root.title("BeatStars Sound Sets")
        root.geometry("1100x780")
        root.minsize(880, 660)
        root.configure(background="#f4f6f8")
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background="#f4f6f8")
        style.configure("TLabel", background="#f4f6f8", foreground="#172b3a", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"))
        style.configure("Muted.TLabel", foreground="#506373", font=("Segoe UI", 10))
        style.configure("TButton", padding=(12, 8), font=("Segoe UI", 10))
        style.configure("Primary.TButton", background="#176e66", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#135c55"), ("disabled", "#a2b5b2")])
        style.configure("Treeview", font=("Segoe UI", 11), rowheight=34,
                        background="#ffffff", fieldbackground="#ffffff", foreground="#172b3a")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=(8, 8))
        style.map("Treeview", background=[("selected", "#176e66")], foreground=[("selected", "white")])
        style.configure("TEntry", padding=6)
        style.configure("TCombobox", padding=6)

        outer = ttk.Frame(root, padding=24)
        outer.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)

        ttk.Label(outer, text="BeatStars Sound Sets", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(outer, text="Sound choices linked to chart references, ready as named MIDI lanes.",
                  style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 18))

        controls = ttk.Frame(outer)
        controls.grid(row=2, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)
        ttk.Button(controls, text="Choose observations CSV…", command=self._choose_csv).grid(row=0, column=0, sticky="w")
        ttk.Label(controls, textvariable=self.source_name, style="Muted.TLabel").grid(row=0, column=1, sticky="w", padx=12)
        ttk.Label(controls, text="Observed on").grid(row=0, column=2, padx=(12, 6))
        ttk.Entry(controls, textvariable=self.observed_at, width=12).grid(row=0, column=3)
        ttk.Label(controls, text="YYYY-MM-DD", style="Muted.TLabel").grid(row=1, column=3, sticky="w", pady=(3, 0))
        ttk.Label(controls, text="Chart view").grid(row=0, column=4, padx=(18, 6))
        scope = ttk.Combobox(controls, textvariable=self.scope_label, values=list(SCOPE_LABELS), state="readonly", width=20)
        scope.grid(row=0, column=5, sticky="e")
        scope.bind("<<ComboboxSelected>>", lambda _: self._refresh_sets())

        facts = ttk.Frame(outer, padding=(0, 15, 0, 12))
        facts.grid(row=3, column=0, sticky="ew")
        ttk.Label(facts, text="Dated chart sample • sales are not verified • MIDI lanes only; no audio",
                  style="Muted.TLabel").pack(anchor="w")
        ttk.Label(facts, textvariable=self.summary).pack(anchor="w", pady=(5, 0))

        content = ttk.Panedwindow(outer, orient="horizontal")
        content.grid(row=4, column=0, sticky="nsew")
        left = ttk.Frame(content, padding=(0, 0, 12, 0))
        right = ttk.Frame(content, padding=(12, 0, 0, 0))
        content.add(left, weight=2)
        content.add(right, weight=3)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ttk.Label(left, text="Find a style or sound").grid(row=0, column=0, sticky="w", pady=(0, 5))
        ttk.Entry(left, textvariable=self.search).grid(row=1, column=0, sticky="ew", pady=(0, 10))
        list_frame = ttk.Frame(left)
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(list_frame, columns=("style", "references"), show="headings", selectmode="extended")
        self.tree.heading("style", text="Matched style", anchor="w")
        self.tree.heading("references", text="Refs", anchor="center")
        self.tree.column("style", width=270, minwidth=170, stretch=True)
        self.tree.column("references", width=55, minwidth=48, stretch=False, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _: self._show_details())
        ttk.Label(left, text="Ctrl-click to choose more than one style.", style="Muted.TLabel").grid(row=3, column=0, sticky="w", pady=(8, 0))

        ttk.Label(right, text="Suggested palette & chart references", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
        detail_frame = ttk.Frame(right)
        detail_frame.grid(row=1, column=0, sticky="nsew")
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)
        self.details = tk.Text(detail_frame, wrap="word", state="disabled", borderwidth=0,
                               background="#ffffff", foreground="#172b3a", padx=16, pady=14,
                               font=("Segoe UI", 10), spacing1=3, spacing3=5, width=50)
        self.details.grid(row=0, column=0, sticky="nsew")
        detail_scroll = ttk.Scrollbar(detail_frame, orient="vertical", command=self.details.yview)
        detail_scroll.grid(row=0, column=1, sticky="ns")
        self.details.configure(yscrollcommand=detail_scroll.set)
        self.details.tag_configure("heading", font=("Segoe UI", 15, "bold"), spacing3=12)
        self.details.tag_configure("section", font=("Segoe UI", 10, "bold"), spacing1=14)

        actions = ttk.Frame(outer, padding=(0, 18, 0, 0))
        actions.grid(row=5, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        ttk.Label(actions, text="Every matched style in this chart view is included by “Generate all”.",
                  style="Muted.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        self.generate_all = ttk.Button(actions, text="Generate all matched", style="Primary.TButton",
                                       command=lambda: self._generate(all_matched=True), state="disabled")
        self.generate_all.grid(row=1, column=1, padx=(10, 0))
        self.generate_selected = ttk.Button(actions, text="Generate selected", command=lambda: self._generate(all_matched=False), state="disabled")
        self.generate_selected.grid(row=1, column=2, padx=(10, 0))
        ttk.Label(actions, textvariable=self.status, style="Muted.TLabel", wraplength=550).grid(row=1, column=0, sticky="w")

    def _load_initial(self):
        try:
            self.palettes = load_palettes()
            if not self.source_path.is_file():
                self._refresh_sets()
                self.status.set("Choose your observations CSV to begin. No chart data is bundled.")
                return
            self.rows = load_rows(self.source_path)
            self._refresh_sets()
        except Exception as exc:
            self.summary.set("The local observations CSV could not be loaded.")
            self.status.set("Choose an observations CSV to continue.")
            messagebox.showerror("Could not load sound sets", str(exc), parent=self.root)

    def _choose_csv(self):
        chosen = filedialog.askopenfilename(parent=self.root, title="Choose chart observations",
            initialdir=str(self.source_path.parent), filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not chosen:
            return
        try:
            new_rows = load_rows(chosen)
            new_palettes = self.palettes or load_palettes()
        except Exception as exc:
            messagebox.showerror("Could not read this CSV", str(exc), parent=self.root)
            return
        observed = simpledialog.askstring("When was this chart observed?",
            "Enter the date these observations were collected (YYYY-MM-DD).\nYou can also edit this date in the main window.",
            initialvalue=self.observed_at.get(), parent=self.root)
        if observed is None:
            return
        try:
            observed = date.fromisoformat(observed.strip()).isoformat()
        except ValueError:
            messagebox.showerror("Check the observation date", "Enter a valid date in YYYY-MM-DD format, such as 2026-09-15.", parent=self.root)
            return
        self.source_path = Path(chosen)
        self.rows, self.palettes = new_rows, new_palettes
        self.source_name.set(self.source_path.name)
        self.observed_at.set(observed)
        self._refresh_sets()

    def _refresh_sets(self):
        try:
            self.active, self.unmatched = select_sets(self.rows, self.palettes, self.scope)
        except Exception as exc:
            self.active, self.unmatched = [], []
            messagebox.showerror("Could not match this snapshot", str(exc), parent=self.root)
        included = [row for row in self.rows if self.scope == "all" or row["scope"] == self.scope]
        self.summary.set(f"{len(self.active)} matched styles · {len(included)} chart observations · {len(self.unmatched)} observations need review")
        self.generate_all.configure(state="normal" if self.active else "disabled")
        self._filter_list()

    def _filter_list(self):
        previous = set(self.tree.selection())
        query = self.search.get().casefold().strip()
        self.tree.delete(*self.tree.get_children())
        visible = []
        for profile in self.active:
            searchable = " ".join([profile["name"], profile.get("description", ""),
                                   *(item["name"] for item in profile["lanes"]),
                                   *(item["title"] for item in profile["evidence"])])
            if query and query not in searchable.casefold():
                continue
            self.tree.insert("", "end", iid=profile["id"], values=(profile["name"], len(profile["evidence"])))
            visible.append(profile["id"])
        retained = [identifier for identifier in visible if identifier in previous]
        if retained:
            self.tree.selection_set(retained)
        elif visible:
            self.tree.selection_set(visible[0])
        self.status.set(f"Showing {len(visible)} of {len(self.active)} matched styles. Search only changes the list.")
        self._show_details()

    def _show_details(self):
        selected = self.tree.selection()
        self.generate_selected.configure(state="normal" if selected else "disabled")
        profile = next((item for item in self.active if item["id"] in selected), None)
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        if profile is None:
            self.details.insert("end", "Choose a style to see its suggested sounds and chart references.\n\nNo results? Clear the search or choose another chart view.")
        else:
            self.details.insert("end", profile["name"] + "\n", "heading")
            if len(selected) > 1:
                self.details.insert("end", f"{len(selected)} styles selected. Showing this style’s details.\n\n")
            self.details.insert("end", profile["description"] + "\n")
            self.details.insert("end", f"Suggested starting tempo: {profile['bpm_hint']}\nSet tempo yourself in FL Studio.\n")
            self.details.insert("end", "SOUND CHOICES\n", "section")
            for item in profile["lanes"]:
                self.details.insert("end", "• " + item["name"] + "\n")
            self.details.insert("end", "CHART REFERENCES\n", "section")
            for reference in profile["evidence"]:
                chart = "Recent releases" if reference["scope"] == "recent_releases" else "All time"
                rank = f" · #{reference['rank']}" if reference["rank"] else " · rank not captured"
                self.details.insert("end", f"{reference['title']}\n{reference['producer']} · {chart}{rank}\n{reference['url']}\n\n")
            self.details.insert("end", "ABOUT THIS SET\n", "section")
            self.details.insert("end", "Sound choices are suggestions inferred from titles and tags; reference audio was not analyzed. The chart sample does not verify sales or cover the entire market.\n\nThe export contains named MIDI lanes with tiny placeholder notes and a role map. Assign your own samples or instruments. Updated chart data must be supplied as an observations CSV.")
        self.details.configure(state="disabled")
        self.details.yview_moveto(0)

    def _generate(self, all_matched):
        # The all-matched branch deliberately ignores search results and selection.
        chosen = None if all_matched else set(self.tree.selection())
        if not self.active or (chosen is not None and not chosen):
            messagebox.showinfo("Choose a sound set", "Select at least one matched style first.", parent=self.root)
            return
        try:
            observed = date.fromisoformat(self.observed_at.get().strip()).isoformat()
        except ValueError:
            messagebox.showerror("Check the observation date", "Enter a valid date in YYYY-MM-DD format, such as 2026-09-15.", parent=self.root)
            return
        destination = filedialog.askdirectory(parent=self.root, title="Choose where to save your sound sets",
            initialdir=str(BASE / "Generated Sets"), mustexist=False)
        if not destination:
            return
        self.generate_all.configure(state="disabled")
        self.generate_selected.configure(state="disabled")
        self.root.configure(cursor="watch")
        self.status.set("Creating your sound sets…")
        self.root.update_idletasks()
        try:
            folder, report = export_collection(destination, self.rows, self.palettes, observed,
                                               scope=self.scope, chosen=chosen)
        except Exception as exc:
            self.status.set("Export could not be completed.")
            messagebox.showerror("Could not generate the sound sets", str(exc), parent=self.root)
            return
        finally:
            self.root.configure(cursor="")
            self.generate_all.configure(state="normal" if self.active else "disabled")
            self.generate_selected.configure(state="normal" if self.tree.selection() else "disabled")
        self.observed_at.set(observed)
        self.status.set(f"Saved {report['sets']} sound sets in {folder.name}.")
        page = (folder / "START HERE.html").resolve()
        try:
            opened = webbrowser.open(page.as_uri())
        except Exception:
            opened = False
        if not opened:
            messagebox.showinfo("Your sound sets are ready", f"Saved {report['sets']} sound sets.\n\nOpen START HERE.html in:\n{folder}", parent=self.root)


def main():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print("The window interface could not start:", exc)
        print("Install Tkinter, or use the command line:")
        print("python generator.py --csv observations.csv --date YYYY-MM-DD --output exports")
        return
    SoundSetApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
