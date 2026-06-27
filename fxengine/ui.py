"""Small manual-test UI for the FXName Engine v0.3 scaffold."""

from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from fxengine.example_retrieval import ExampleRetriever
from fxengine.metadata_writer import MetadataWriter
from fxengine.normalizer import FXNameNormalizer
from fxengine.personal_dictionary import PersonalDictionary
from fxengine.preferences import FXPreferences, PreferenceStore


APP_DATA_DIR = Path.home() / ".sounddesign_translater"


class FXNameEngineApp:
    """Readable inspection surface for Normalize, review, and scaffold outputs."""

    def __init__(self, root: tk.Tk, data_dir: Path = APP_DATA_DIR) -> None:
        self.root = root
        self.personal_dictionary = PersonalDictionary(data_dir / "personal_dictionary.json")
        self.preference_store = PreferenceStore(data_dir / "preferences.json")
        self.normalizer = FXNameNormalizer(personal_dictionary=self.personal_dictionary)
        self.metadata_writer = MetadataWriter()
        self.example_retriever = ExampleRetriever()
        self.last_result = None

        self.output_var = tk.StringVar()
        self.preset_var = tk.StringVar(value="Default")
        self.allow_distance_var = tk.BooleanVar(value=True)

        self._setup_window()
        self._build_ui()

    def _setup_window(self) -> None:
        self.root.title("FXName Engine v0.3 Manual Test")
        self.root.geometry("1040x780")
        self.root.minsize(820, 640)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(5, weight=1)

        controls = ttk.Frame(main)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        controls.columnconfigure(5, weight=1)
        ttk.Label(controls, text="Mode").grid(row=0, column=0, sticky="w")
        ttk.Label(controls, text="FXName Normalize").grid(
            row=0, column=1, sticky="w", padx=(8, 18)
        )
        ttk.Label(controls, text="Preference Preset").grid(row=0, column=2, sticky="w")
        presets = self.preference_store.names()
        preset_box = ttk.Combobox(
            controls,
            textvariable=self.preset_var,
            values=presets,
            state="readonly",
            width=20,
        )
        preset_box.grid(row=0, column=3, padx=(8, 12))
        preset_box.bind("<<ComboboxSelected>>", self._on_preset_changed)
        ttk.Checkbutton(
            controls,
            text="Allow distance in FXName",
            variable=self.allow_distance_var,
        ).grid(row=0, column=4, sticky="w")
        ttk.Button(controls, text="Normalize", command=self.normalize).grid(
            row=0, column=6, sticky="e", padx=(0, 6)
        )
        ttk.Button(controls, text="Reload / Re-normalize", command=self.reload).grid(
            row=0, column=7, sticky="e"
        )

        ttk.Label(main, text="Input").grid(row=1, column=0, sticky="w")
        self.input_text = tk.Text(main, height=4, wrap="word")
        self.input_text.grid(row=2, column=0, sticky="ew", pady=(4, 10))

        output = ttk.Frame(main)
        output.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="FXName Output").grid(row=0, column=0, sticky="w")
        ttk.Entry(output, textvariable=self.output_var, state="readonly").grid(
            row=0, column=1, sticky="ew", padx=8
        )
        ttk.Button(output, text="Copy", command=self._copy_fxname).grid(row=0, column=2)

        ttk.Label(main, text="Token Review").grid(row=4, column=0, sticky="w")
        review = ttk.Frame(main)
        review.grid(row=5, column=0, sticky="nsew", pady=(4, 10))
        review.columnconfigure(0, weight=1)
        review.rowconfigure(0, weight=1)
        columns = (
            "raw",
            "canonical",
            "slot",
            "status",
            "confidence",
            "issues",
            "source",
        )
        self.token_tree = ttk.Treeview(review, columns=columns, show="headings", height=8)
        for column, heading, width in (
            ("raw", "Raw", 130),
            ("canonical", "Canonical", 180),
            ("slot", "Slot", 90),
            ("status", "Status", 110),
            ("confidence", "Confidence", 90),
            ("issues", "Issues", 160),
            ("source", "Source", 135),
        ):
            self.token_tree.heading(column, text=heading)
            self.token_tree.column(column, width=width, anchor="w")
        self.token_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(review, orient="vertical", command=self.token_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.token_tree.configure(yscrollcommand=scrollbar.set)
        self.token_tree.tag_configure("unknown", foreground="#b00020")
        self.token_tree.tag_configure("needs_review", foreground="#9a6700")

        actions = ttk.Frame(review)
        actions.grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(actions, text="Map Selected", command=self._map_selected).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(actions, text="Keep Raw", command=self._keep_selected).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(actions, text="Ignore", command=self._ignore_selected).pack(side="left")
        ttk.Button(
            actions,
            text="Remove Selected Alias",
            command=self._remove_selected_alias,
        ).pack(side="left", padx=(6, 0))

        lower = ttk.Frame(main)
        lower.grid(row=6, column=0, sticky="nsew")
        for column in range(3):
            lower.columnconfigure(column, weight=1)

        self.description_text = self._text_panel(lower, 0, "Description Output")
        ttk.Button(lower, text="Copy Description", command=self._copy_description).grid(
            row=2, column=0, sticky="w", pady=(4, 0)
        )
        self.references_text = self._text_panel(lower, 1, "Suggestions / References")
        self.issues_text = self._text_panel(lower, 2, "Issues")

    @staticmethod
    def _text_panel(parent: ttk.Frame, column: int, title: str) -> tk.Text:
        ttk.Label(parent, text=title).grid(row=0, column=column, sticky="w", padx=(0, 8))
        text = tk.Text(parent, height=7, wrap="word", state="disabled")
        text.grid(row=1, column=column, sticky="nsew", padx=(0, 8), pady=(4, 0))
        return text

    def _selected_preferences(self) -> FXPreferences:
        profile = self.preference_store.get(self.preset_var.get())
        return replace(
            profile,
            allow_distance_in_fxname=self.allow_distance_var.get(),
            preserve_order=True,
            boom_can_reorder=False,
            boom_suggestion_only=True,
        )

    def normalize(self) -> None:
        input_text = self.input_text.get("1.0", "end").strip()
        result = self.normalizer.normalize(input_text, self._selected_preferences())
        self.last_result = result
        self.output_var.set(result.output_fxname)
        self._show_tokens(result.tokens)

        examples = self.example_retriever.retrieve(result.output_fxname)
        metadata = self.metadata_writer.write(
            result.output_fxname,
            source_tokens=result.tokens,
            references=examples.examples,
        )
        description = metadata.description or f"[{metadata.issues[0]}] needs review"
        suggestions = list(result.suggestions) + list(examples.examples)
        if not suggestions:
            suggestions = ["No suggestion/reference returned"]
        self._set_text(self.description_text, description)
        self._set_text(self.references_text, "\n".join(suggestions))
        self._set_text(
            self.issues_text,
            "\n".join(self._display_issue(issue) for issue in result.issues) or "None",
        )

    def _show_tokens(self, tokens) -> None:
        for item in self.token_tree.get_children():
            self.token_tree.delete(item)
        for token in tokens:
            tag = token.status if token.status in {"unknown", "needs_review"} else ""
            self.token_tree.insert(
                "",
                "end",
                values=(
                    token.raw,
                    token.text,
                    token.slot,
                    token.status,
                    f"{token.confidence:.2f}",
                    ", ".join(token.issues),
                    token.source,
                ),
                tags=(tag,) if tag else (),
            )

    def _selected_raw(self) -> str | None:
        selection = self.token_tree.selection()
        if not selection:
            messagebox.showinfo("Token Review", "Select a token first.")
            return None
        values = self.token_tree.item(selection[0], "values")
        return str(values[0]) if values else None

    def _map_selected(self) -> None:
        raw = self._selected_raw()
        if not raw:
            return
        canonical = simpledialog.askstring(
            "Map token",
            f"Canonical FXName token(s) for {raw!r}:",
            initialvalue="",
            parent=self.root,
        )
        if canonical and canonical.strip():
            self.personal_dictionary.add_alias(raw, canonical)
            self.normalize()

    def _keep_selected(self) -> None:
        raw = self._selected_raw()
        if raw:
            self.personal_dictionary.keep_raw(raw)
            self.normalize()

    def _ignore_selected(self) -> None:
        raw = self._selected_raw()
        if raw:
            self.personal_dictionary.ignore(raw)
            self.normalize()

    def _remove_selected_alias(self) -> None:
        raw = self._selected_raw()
        if not raw:
            return
        if self.personal_dictionary.remove_alias(raw):
            self.normalize()
        else:
            messagebox.showinfo("Token Review", f"No personal alias saved for {raw!r}.")

    def reload(self) -> None:
        self.personal_dictionary.load()
        self.normalizer = FXNameNormalizer(
            personal_dictionary=self.personal_dictionary,
        )
        self.normalize()

    def _on_preset_changed(self, _event=None) -> None:
        profile = self.preference_store.get(self.preset_var.get())
        self.allow_distance_var.set(profile.allow_distance_in_fxname)
        if self.input_text.get("1.0", "end").strip():
            self.normalize()

    def _copy_fxname(self) -> None:
        self._copy(self.output_var.get())

    def _copy_description(self) -> None:
        self._copy(self.description_text.get("1.0", "end").strip())

    def _copy(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    @staticmethod
    def _display_issue(issue: str) -> str:
        if ":" not in issue:
            return issue
        name, value = issue.split(":", 1)
        return f"{name}: {value.strip()}"


def main() -> None:
    root = tk.Tk()
    FXNameEngineApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
