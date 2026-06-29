"""离线翻译引擎 · 独立测试前端（Tkinter）。

用于在接入 UCSRenamer 之前手动测试 4 种能力，可用 PyInstaller 打包为单应用。
模型懒加载：窗口秒开，首次翻译时后台加载 NLLB。

打包见 tools/build_gui.ps1。
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk

TITLE = "SoundDesign Translator · 测试台"

MODES = [
    ("中文 → FXName 风格英文（命名）", "fxname"),
    ("中文 → 英文整句（写 metadata）", "zh_to_en"),
    ("英文 → 中文（词/句，意思到位）", "en_to_zh"),
]

SAMPLES = {
    "fxname": "玻璃杯清脆碰撞",
    "zh_to_en": "远处传来沉闷的雷声，伴随金属门缓缓关闭。",
    "en_to_zh": "Heavy metal door slam with reverberant tail.",
}


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.task = tk.StringVar(value="fxname")
        self.show_trace = tk.BooleanVar(value=True)
        self._build()
        self.root.after(80, self._poll)

    def _build(self) -> None:
        self.root.title(TITLE)
        self.root.geometry("760x640")
        self.root.minsize(620, 520)
        pad = {"padx": 10, "pady": 6}

        top = ttk.LabelFrame(self.root, text="模式")
        top.pack(fill="x", **pad)
        for label, value in MODES:
            ttk.Radiobutton(
                top, text=label, value=value, variable=self.task,
                command=self._on_mode,
            ).pack(anchor="w", padx=8, pady=2)
        ttk.Checkbutton(
            top, text="显示 token 轨迹（仅 FXName）", variable=self.show_trace
        ).pack(anchor="w", padx=8, pady=2)

        inf = ttk.LabelFrame(self.root, text="输入（Ctrl+Enter 翻译）")
        inf.pack(fill="both", expand=True, **pad)
        self.inp = tk.Text(inf, height=6, wrap="word", font=("Consolas", 11))
        self.inp.pack(fill="both", expand=True, padx=6, pady=6)
        self.inp.insert("1.0", SAMPLES["fxname"])
        self.inp.bind("<Control-Return>", lambda e: self._go())

        btns = ttk.Frame(self.root)
        btns.pack(fill="x", **pad)
        self.go_btn = ttk.Button(btns, text="翻译", command=self._go)
        self.go_btn.pack(side="left")
        ttk.Button(btns, text="复制结果", command=self._copy).pack(side="left", padx=6)
        ttk.Button(btns, text="清空", command=lambda: self.inp.delete("1.0", "end")).pack(side="left")

        outf = ttk.LabelFrame(self.root, text="输出")
        outf.pack(fill="both", expand=True, **pad)
        self.out = tk.Text(outf, height=12, wrap="word", font=("Consolas", 11),
                           state="disabled", background="#f6f6f6")
        self.out.pack(fill="both", expand=True, padx=6, pady=6)

        self.status = ttk.Label(self.root, text="就绪（模型首次翻译时加载）", anchor="w")
        self.status.pack(fill="x", side="bottom")

    def _on_mode(self) -> None:
        cur = self.inp.get("1.0", "end").strip()
        if cur in SAMPLES.values() or not cur:
            self.inp.delete("1.0", "end")
            self.inp.insert("1.0", SAMPLES[self.task.get()])

    def _set_out(self, text: str) -> None:
        self.out.config(state="normal")
        self.out.delete("1.0", "end")
        self.out.insert("1.0", text)
        self.out.config(state="disabled")

    def _copy(self) -> None:
        text = self.out.get("1.0", "end").strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text.splitlines()[0])
            self.status.config(text="已复制首行到剪贴板")

    def _go(self) -> None:
        text = self.inp.get("1.0", "end").strip()
        if not text:
            return
        task = self.task.get()
        self.go_btn.config(state="disabled")
        self.status.config(text="翻译中…（首次需加载模型，请稍候）")
        threading.Thread(target=self._work, args=(text, task, self.show_trace.get()),
                         daemon=True).start()

    def _work(self, text: str, task: str, trace: bool) -> None:
        try:
            from translator import api
            res = api.translate(text, task=task)
            body = res.text
            if task == "fxname" and trace and res.detail is not None:
                lines = ["", "── token 轨迹 ──"]
                for t in res.detail.traces:
                    lines.append(
                        f"{t.source_text}  →  {t.translated}"
                        + (f"  ⇒ {t.snapped}" if t.snapped and t.snapped != t.translated else "")
                        + (f"   [{t.decision}]" if t.decision else "")
                    )
                body = body + "\n" + "\n".join(lines)
            self.q.put(("ok", body))
        except Exception as exc:  # noqa: BLE001
            self.q.put(("err", f"{type(exc).__name__}: {exc}"))

    def _poll(self) -> None:
        try:
            kind, payload = self.q.get_nowait()
        except queue.Empty:
            pass
        else:
            self.go_btn.config(state="normal")
            if kind == "ok":
                self._set_out(payload)
                self.status.config(text="完成")
            else:
                self._set_out(payload)
                self.status.config(text="出错")
        self.root.after(80, self._poll)


def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
