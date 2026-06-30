"""FXName-only desktop app.

This entry point intentionally avoids importing ``engine`` / NLLB modules so the
default installer can ship without the local AI model.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from translator import fxname_mode


class FXNameApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SoundDesign FXName Translator")
        self.root.geometry("860x620")
        self.root.minsize(680, 500)

        self.input_text: tk.Text
        self.output_text: tk.Text
        self.trace_text: tk.Text
        self.status_var = tk.StringVar(value="Ready")

        self._build_ui()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            main,
            text="中文/中英混合 -> BOOM 风格 FXName",
            font=("Microsoft YaHei UI", 14, "bold"),
        )
        title.pack(anchor=tk.W)

        hint = ttk.Label(
            main,
            text="离线词典版：不加载 NLLB 模型；词典未命中会略去并在 Trace 中标 unknown。",
        )
        hint.pack(anchor=tk.W, pady=(4, 10))

        panes = ttk.PanedWindow(main, orient=tk.VERTICAL)
        panes.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.Labelframe(panes, text="输入")
        self.input_text = tk.Text(input_frame, height=7, wrap=tk.WORD, undo=True)
        self.input_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        panes.add(input_frame, weight=2)

        output_frame = ttk.Labelframe(panes, text="FXName 输出")
        self.output_text = tk.Text(output_frame, height=4, wrap=tk.WORD)
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        panes.add(output_frame, weight=1)

        trace_frame = ttk.Labelframe(panes, text="Token Trace")
        self.trace_text = tk.Text(trace_frame, height=10, wrap=tk.NONE)
        yscroll = ttk.Scrollbar(trace_frame, orient=tk.VERTICAL, command=self.trace_text.yview)
        self.trace_text.configure(yscrollcommand=yscroll.set)
        self.trace_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=8)
        panes.add(trace_frame, weight=3)

        actions = ttk.Frame(main)
        actions.pack(fill=tk.X, pady=(10, 0))

        translate_btn = ttk.Button(actions, text="Translate FXName", command=self.translate)
        translate_btn.pack(side=tk.LEFT)

        clear_btn = ttk.Button(actions, text="Clear", command=self.clear)
        clear_btn.pack(side=tk.LEFT, padx=(8, 0))

        copy_btn = ttk.Button(actions, text="Copy Output", command=self.copy_output)
        copy_btn.pack(side=tk.LEFT, padx=(8, 0))

        status = ttk.Label(actions, textvariable=self.status_var)
        status.pack(side=tk.RIGHT)

        self.root.bind("<Control-Return>", lambda _event: self.translate())

    def translate(self) -> None:
        text = self.input_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("No input", "请输入中文或中英混合音效描述。")
            return

        self.status_var.set("Translating...")
        threading.Thread(target=self._translate_worker, args=(text,), daemon=True).start()

    def _translate_worker(self, text: str) -> None:
        try:
            result = fxname_mode.normalize(text)
        except Exception as exc:  # pragma: no cover - UI safety net
            self.root.after(0, self._show_error, exc)
            return
        self.root.after(0, self._show_result, result)

    def _show_result(self, result: fxname_mode.FXResult) -> None:
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", result.output_fxname)

        lines: list[str] = []
        for trace in result.traces:
            if trace.kind == "ascii":
                lines.append(
                    f"{trace.source_text}\tASCII\t{trace.decision}\t"
                    f"{' '.join(trace.final_words)}"
                )
                continue
            lines.append(
                f"{trace.source_text}\t{trace.decision or '-'}\t"
                f"{trace.translated or '∅'}\t{trace.snapped or '-'}\t"
                f"{' '.join(trace.final_words)}"
            )

        self.trace_text.delete("1.0", tk.END)
        self.trace_text.insert("1.0", "\n".join(lines))
        self.status_var.set("Done")

    def _show_error(self, exc: Exception) -> None:
        self.status_var.set("Error")
        messagebox.showerror("Translate failed", str(exc))

    def clear(self) -> None:
        self.input_text.delete("1.0", tk.END)
        self.output_text.delete("1.0", tk.END)
        self.trace_text.delete("1.0", tk.END)
        self.status_var.set("Ready")

    def copy_output(self) -> None:
        text = self.output_text.get("1.0", tk.END).strip()
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("Copied")


def main() -> None:
    root = tk.Tk()
    FXNameApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
