"""NLLB 本地翻译测试工具 — tkinter GUI。"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from engine import ModelNotFoundError, NllbTranslator, TranslateMode, TranslationError, TranslationResult


class TranslateApp:
    """中英互译测试界面（输入语言自动检测 + 音频专业模式）。"""

    MODE_OPTIONS = [
        ("自动", TranslateMode.AUTO),
        ("句子", TranslateMode.SENTENCE),
        ("文件名", TranslateMode.FILENAME),
    ]

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.translator = NllbTranslator()
        self.mode_var = tk.StringVar(value="自动")
        self.pro_mode_var = tk.BooleanVar(value=True)

        self._setup_window()
        self._build_ui()
        self._start_model_loading()

    def _setup_window(self) -> None:
        self.root.title("NLLB 本地翻译工具")
        self.root.geometry("760x580")
        self.root.minsize(520, 420)

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.input_label = ttk.Label(main_frame, text="输入（中/英自动识别）")
        self.input_label.pack(anchor=tk.W)

        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

        self.input_box = tk.Text(input_frame, wrap=tk.WORD, height=10, font=("Microsoft YaHei UI", 11))
        input_scroll = ttk.Scrollbar(input_frame, orient=tk.VERTICAL, command=self.input_box.yview)
        self.input_box.configure(yscrollcommand=input_scroll.set)
        self.input_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        input_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(ctrl_frame, text="模式:").pack(side=tk.LEFT)
        mode_combo = ttk.Combobox(
            ctrl_frame,
            textvariable=self.mode_var,
            values=[label for label, _ in self.MODE_OPTIONS],
            state="readonly",
            width=8,
        )
        mode_combo.pack(side=tk.LEFT, padx=(4, 12))

        ttk.Checkbutton(
            ctrl_frame,
            text="音频专业模式",
            variable=self.pro_mode_var,
        ).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=4)

        self.translate_btn = ttk.Button(
            btn_frame,
            text="翻 译",
            command=self._on_translate_click,
            state=tk.DISABLED,
        )
        self.translate_btn.pack()

        self.output_label = ttk.Label(main_frame, text="输出")
        self.output_label.pack(anchor=tk.W)

        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

        self.output_box = tk.Text(
            output_frame,
            wrap=tk.WORD,
            height=10,
            font=("Segoe UI", 11),
            state=tk.DISABLED,
        )
        output_scroll = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.output_box.yview)
        self.output_box.configure(yscrollcommand=output_scroll.set)
        self.output_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        output_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_label = ttk.Label(main_frame, text="正在加载本地模型...", anchor=tk.W)
        self.status_label.pack(fill=tk.X, pady=(4, 0))

    def _get_selected_mode(self) -> TranslateMode:
        label = self.mode_var.get()
        for opt_label, mode in self.MODE_OPTIONS:
            if opt_label == label:
                return mode
        return TranslateMode.AUTO

    def _set_status(self, message: str) -> None:
        self.status_label.config(text=message)

    def _schedule_status(self, message: str) -> None:
        self.root.after(0, lambda msg=message: self._set_status(msg))

    def _start_model_loading(self) -> None:
        def _load_worker() -> None:
            def on_progress(msg: str) -> None:
                self._schedule_status(msg)

            try:
                self.translator.load(on_progress=on_progress)
                self.root.after(0, self._on_model_loaded)
            except ModelNotFoundError as exc:
                self.root.after(0, lambda err=str(exc): self._on_model_load_failed(err))

        threading.Thread(target=_load_worker, daemon=True).start()

    def _on_model_loaded(self) -> None:
        self.translate_btn.config(state=tk.NORMAL)
        if not self.translator.glossary_ready:
            self._set_status("模型已就绪；术语库未构建，请运行 build_glossary.py")
            messagebox.showwarning(
                "术语库缺失",
                f"{self.translator.glossary_error}\n\n音频专业模式需要先构建术语库。",
            )
        else:
            self._set_status("模型与术语库已就绪")

    def _on_model_load_failed(self, err_msg: str) -> None:
        self._set_status("模型加载失败")
        messagebox.showerror(
            "模型加载失败",
            f"{err_msg}\n\n请将 CTranslate2 转换后的 NLLB int8 模型放入 nllb_int8_model 目录。",
        )

    def _on_translate_click(self) -> None:
        input_text = self.input_box.get("1.0", "end-1c")
        if not input_text.strip():
            return

        if self.pro_mode_var.get() and not self.translator.glossary_ready:
            messagebox.showwarning("术语库缺失", self.translator.glossary_error or "请先构建术语库")
            return

        self.translate_btn.config(state=tk.DISABLED)
        self._set_status("翻译中...")

        mode = self._get_selected_mode()
        pro_mode = self.pro_mode_var.get()

        def _worker() -> None:
            try:
                result = self.translator.translate(input_text, mode=mode, pro_mode=pro_mode)
                self.root.after(0, lambda r=result: self._update_ui_success(r))
            except (TranslationError, Exception) as exc:
                self.root.after(0, lambda err=str(exc): self._update_ui_error(err))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_ui_success(self, result: TranslationResult) -> None:
        self.output_box.config(state=tk.NORMAL)
        self.output_box.delete("1.0", tk.END)
        self.output_box.insert("1.0", result.text)
        self.output_box.config(state=tk.DISABLED)
        self._set_status(f"翻译完成 ({result.status_label})")
        self.translate_btn.config(state=tk.NORMAL)

    def _update_ui_error(self, err_msg: str) -> None:
        self._set_status("翻译出错")
        self.translate_btn.config(state=tk.NORMAL)
        messagebox.showerror("错误", err_msg)


def main() -> None:
    root = tk.Tk()
    TranslateApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
