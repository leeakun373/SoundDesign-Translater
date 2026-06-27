"""Small manual-test UI for the FXName Engine v0.3 scaffold."""

from __future__ import annotations

import tkinter as tk
from collections import Counter
from dataclasses import replace
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from fxengine.example_retrieval import ExampleRetriever
from fxengine.metadata_writer import MetadataWriter
from fxengine.models import FXToken
from fxengine.normalizer import FXNameNormalizer
from fxengine.personal_dictionary import PersonalDictionary
from fxengine.preferences import FXPreferences, PreferenceStore


APP_DATA_DIR = Path.home() / ".sounddesign_translater"
PRESET_LABELS = {
    "Default": "默认",
    "No Distance": "不保留距离",
    "Strict Review": "严格审核",
    "Keep Raw Friendly": "保留英文原词",
}
DECISION_LABELS = {
    "mapped_personal": "已映射（个人词典）",
    "mapped_canonical": "已映射（标准词库）",
    "mapped_glossary": "已映射（术语库）",
    "kept_raw": "保留原词",
    "unknown": "未识别",
    "ignored_pollution": "已忽略（污染内容）",
    "ignored_personal": "已忽略（个人设置）",
    "metadata_candidate": "元数据候选",
}
SOURCE_LABELS = {
    "personal_dictionary": "个人词典",
    "canonical_csv": "标准词库（Canonical CSV）",
    "glossary_fallback": "术语库回退",
    "keep_raw_rule": "保留原词规则",
    "technical_token_rule": "技术 Token 规则",
    "pollution_filter": "污染过滤",
    "unknown_review": "未识别审核",
    "distance_rule": "距离规则",
}
SLOT_LABELS = {
    "material": "材质",
    "object": "物体",
    "source": "声源",
    "action": "动作",
    "motion": "运动",
    "detail": "细节",
    "modifier": "修饰",
    "unknown": "未知",
    "ignored": "已忽略",
}
ISSUE_LABELS = {
    "unknown_ascii": "未识别英文 / ASCII",
    "unknown_zh": "未识别中文",
    "unsafe_fragment_rejected": "已过滤污染短语",
    "distance_excluded": "距离已移至元数据候选",
    "technical_token_excluded": "技术 Token 已移至元数据候选",
    "empty_output": "没有可用的 FXName 输出",
}
QUALITY_LABELS = {
    "pass": "通过",
    "needs_review": "需要审核",
    "fail": "失败",
}


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
        self.preset_var = tk.StringVar(value=PRESET_LABELS["Default"])
        self.allow_distance_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="就绪：输入内容后按 Enter 生成 FXName")

        self._setup_window()
        self._build_ui()

    def _setup_window(self) -> None:
        self.root.title("FXName Engine v0.3 音效命名工具")
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
        ttk.Label(controls, text="模式").grid(row=0, column=0, sticky="w")
        ttk.Label(controls, text="FXName 标准化").grid(
            row=0, column=1, sticky="w", padx=(8, 18)
        )
        ttk.Label(controls, text="偏好预设").grid(row=0, column=2, sticky="w")
        presets = [self._preset_label(name) for name in self.preference_store.names()]
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
            text="FXName 中保留距离",
            variable=self.allow_distance_var,
        ).grid(row=0, column=4, sticky="w")
        ttk.Button(controls, text="生成 FXName", command=self.normalize).grid(
            row=0, column=6, sticky="e", padx=(0, 6)
        )
        ttk.Button(controls, text="重新加载 / 生成", command=self.reload).grid(
            row=0, column=7, sticky="e"
        )
        ttk.Label(controls, textvariable=self.status_var).grid(
            row=1, column=0, columnspan=8, sticky="w", pady=(6, 0)
        )

        ttk.Label(main, text="输入（Enter 生成，Shift+Enter 换行）").grid(
            row=1, column=0, sticky="w"
        )
        self.input_text = tk.Text(main, height=4, wrap="word")
        self.input_text.grid(row=2, column=0, sticky="ew", pady=(4, 10))
        self.input_text.bind("<Return>", self._on_input_return)
        self.input_text.bind("<KP_Enter>", self._on_input_return)

        output = ttk.Frame(main)
        output.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="FXName 输出").grid(row=0, column=0, sticky="w")
        ttk.Entry(output, textvariable=self.output_var, state="readonly").grid(
            row=0, column=1, sticky="ew", padx=8
        )
        ttk.Button(output, text="复制", command=self._copy_fxname).grid(row=0, column=2)

        ttk.Label(main, text="Token 审核").grid(row=4, column=0, sticky="w")
        review = ttk.Frame(main)
        review.grid(row=5, column=0, sticky="nsew", pady=(4, 10))
        review.columnconfigure(0, weight=1)
        review.rowconfigure(0, weight=1)
        columns = (
            "raw",
            "canonical",
            "status",
            "source",
            "final",
            "confidence",
            "issues",
            "slot",
        )
        self.token_tree = ttk.Treeview(review, columns=columns, show="headings", height=8)
        for column, heading, width in (
            ("raw", "原始 Token", 130),
            ("canonical", "输出 / 标准词", 175),
            ("status", "状态", 145),
            ("source", "来源", 155),
            ("final", "进入 FXName", 85),
            ("confidence", "置信度", 75),
            ("issues", "问题", 175),
            ("slot", "类别", 70),
        ):
            self.token_tree.heading(column, text=heading)
            self.token_tree.column(column, width=width, anchor="w")
        self.token_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(review, orient="vertical", command=self.token_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.token_tree.configure(yscrollcommand=scrollbar.set)
        self.token_tree.tag_configure("unknown", foreground="#b00020")
        self.token_tree.tag_configure("kept_raw", foreground="#9a6700")
        self.token_tree.tag_configure("ignored_pollution", foreground="#6b7280")
        self.token_tree.tag_configure("ignored_personal", foreground="#6b7280")
        self.token_tree.tag_configure("metadata_candidate", foreground="#6b4fa1")
        self.token_tree.tag_configure("mapped_personal", foreground="#18794e")
        self.token_tree.tag_configure("mapped_canonical", foreground="#155eef")
        self.token_tree.tag_configure("mapped_glossary", foreground="#087e8b")

        actions = ttk.Frame(review)
        actions.grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(actions, text="映射选中项", command=self._map_selected).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(actions, text="保留原词", command=self._keep_selected).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(actions, text="忽略", command=self._ignore_selected).pack(side="left")
        ttk.Button(
            actions,
            text="删除选中映射",
            command=self._remove_selected_alias,
        ).pack(side="left", padx=(6, 0))

        lower = ttk.Frame(main)
        lower.grid(row=6, column=0, sticky="nsew")
        for column in range(3):
            lower.columnconfigure(column, weight=1)

        self.description_text = self._text_panel(lower, 0, "描述输出")
        ttk.Button(lower, text="复制描述", command=self._copy_description).grid(
            row=2, column=0, sticky="w", pady=(4, 0)
        )
        self.references_text = self._text_panel(lower, 1, "建议 / 参考")
        self.issues_text = self._text_panel(lower, 2, "问题")

        self.input_text.focus_set()

    @staticmethod
    def _text_panel(parent: ttk.Frame, column: int, title: str) -> tk.Text:
        ttk.Label(parent, text=title).grid(row=0, column=column, sticky="w", padx=(0, 8))
        text = tk.Text(parent, height=7, wrap="word", state="disabled")
        text.grid(row=1, column=column, sticky="nsew", padx=(0, 8), pady=(4, 0))
        return text

    def _selected_preferences(self) -> FXPreferences:
        profile = self.preference_store.get(self._selected_preset_name())
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
        decisions = Counter(token.decision for token in result.tokens)
        decision_summary = ", ".join(
            f"{self._decision_label(decision)}={count}"
            for decision, count in sorted(decisions.items())
        )
        self.status_var.set(
            f"已生成：{QUALITY_LABELS.get(result.quality, result.quality)}"
            f" | {len(result.tokens)} 个 Token"
            + (f" | {decision_summary}" if decision_summary else "")
        )

        examples = self.example_retriever.retrieve(result.output_fxname)
        metadata = self.metadata_writer.write(
            result.output_fxname,
            source_tokens=result.tokens,
            references=examples.examples,
        )
        description = metadata.description or "[占位功能] 描述生成尚未实现"
        suggestions = list(result.suggestions) + list(examples.examples)
        if not suggestions:
            suggestions = ["暂无建议或参考"]
        self._set_text(self.description_text, description)
        self._set_text(self.references_text, "\n".join(suggestions))
        self._set_text(
            self.issues_text,
            "\n".join(self._display_issue(issue) for issue in result.issues) or "无",
        )

    def _show_tokens(self, tokens) -> None:
        for item in self.token_tree.get_children():
            self.token_tree.delete(item)
        for token in tokens:
            tag = token.decision
            self.token_tree.insert(
                "",
                "end",
                values=(
                    token.raw,
                    token.text,
                    self._review_status(token),
                    self._source_label(token.source),
                    "是" if token.contributes_to_fxname else "否",
                    f"{token.confidence:.2f}",
                    ", ".join(self._display_issue(issue) for issue in token.issues),
                    SLOT_LABELS.get(token.slot, token.slot),
                ),
                tags=(tag,) if tag else (),
            )

    def _selected_raw(self) -> str | None:
        selection = self.token_tree.selection()
        if not selection:
            messagebox.showinfo("Token 审核", "请先选择一个 Token。")
            return None
        values = self.token_tree.item(selection[0], "values")
        return str(values[0]) if values else None

    def _map_selected(self) -> None:
        raw = self._selected_raw()
        if not raw:
            return
        canonical = simpledialog.askstring(
            "映射 Token",
            f"请输入 {raw!r} 对应的标准 FXName 词：",
            initialvalue="",
            parent=self.root,
        )
        if canonical and canonical.strip():
            self.personal_dictionary.add_alias(raw, canonical)
            self.normalize()
            self.status_var.set(f"已保存个人映射：{raw} → {canonical.strip()}")

    def _keep_selected(self) -> None:
        raw = self._selected_raw()
        if raw:
            self.personal_dictionary.keep_raw(raw)
            self.normalize()
            self.status_var.set(f"已设置保留原词：{raw}")

    def _ignore_selected(self) -> None:
        raw = self._selected_raw()
        if raw:
            self.personal_dictionary.ignore(raw)
            self.normalize()
            self.status_var.set(f"已设置忽略：{raw}")

    def _remove_selected_alias(self) -> None:
        raw = self._selected_raw()
        if not raw:
            return
        if self.personal_dictionary.remove_alias(raw):
            self.normalize()
            self.status_var.set(f"已删除个人映射：{raw}")
        else:
            messagebox.showinfo("Token 审核", f"{raw!r} 没有保存个人映射。")

    def reload(self) -> None:
        self.personal_dictionary.load()
        self.normalizer = FXNameNormalizer(
            personal_dictionary=self.personal_dictionary,
        )
        self.normalize()
        if self.last_result is not None:
            self.status_var.set(
                "已重新加载标准词库和个人词典；结果："
                f"{QUALITY_LABELS.get(self.last_result.quality, self.last_result.quality)}"
            )

    def _on_preset_changed(self, _event=None) -> None:
        profile = self.preference_store.get(self._selected_preset_name())
        self.allow_distance_var.set(profile.allow_distance_in_fxname)
        if self.input_text.get("1.0", "end").strip():
            self.normalize()

    def _copy_fxname(self) -> None:
        self._copy(self.output_var.get())
        self.status_var.set("已复制 FXName")

    def _copy_description(self) -> None:
        self._copy(self.description_text.get("1.0", "end").strip())
        self.status_var.set("已复制描述")

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
        name, separator, value = issue.partition(":")
        label = ISSUE_LABELS.get(name, name)
        return f"{label}：{value.strip()}" if separator else label

    @staticmethod
    def _review_status(token: FXToken) -> str:
        value = token.decision or token.status
        return DECISION_LABELS.get(value, value)

    @staticmethod
    def _source_label(source: str) -> str:
        return SOURCE_LABELS.get(source, source)

    @staticmethod
    def _decision_label(decision: str) -> str:
        return DECISION_LABELS.get(decision, decision)

    @staticmethod
    def _preset_label(name: str) -> str:
        return PRESET_LABELS.get(name, name)

    def _selected_preset_name(self) -> str:
        selected = self.preset_var.get()
        for name, label in PRESET_LABELS.items():
            if selected in {name, label}:
                return name
        return selected

    def _on_input_return(self, event) -> str | None:
        if event.state & 0x0001:
            return None
        self.normalize()
        return "break"


def main() -> None:
    root = tk.Tk()
    FXNameEngineApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
