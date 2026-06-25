"""NLLB 本地翻译测试工具 — tkinter GUI。"""



from __future__ import annotations



import threading

import tkinter as tk

from tkinter import messagebox, ttk



from engine import (

    ModelNotFoundError,

    NllbTranslator,

    TaskMode,

    TranslateMode,

    TranslationError,

    TranslationResult,

)





class TranslateApp:

    """中英互译测试界面（输入语言自动检测 + 任务模式边界）。"""



    MODE_OPTIONS = [

        ("自动 / Auto", TranslateMode.AUTO),

        ("句子 / Sentence", TranslateMode.SENTENCE),

        ("文件名 / Filename", TranslateMode.FILENAME),

    ]



    TASK_OPTIONS = [

        ("FXName / 音效命名", TaskMode.FXNAME),

        ("General / 普通翻译", TaskMode.GENERAL),

    ]



    TASK_HINTS = {

        TaskMode.FXNAME: "音效命名：适合声音素材名、FXName、Soundminer/UCS 命名；会过滤口语化 NLLB 输出。",

        TaskMode.GENERAL: "普通翻译：适合句子、说明文本；保留术语分段 + NLLB 句子逻辑。",

    }



    def __init__(self, root: tk.Tk) -> None:

        self.root = root

        self.translator = NllbTranslator()

        self.mode_var = tk.StringVar(value="自动 / Auto")

        self.task_var = tk.StringVar(value="FXName / 音效命名")

        self.pro_mode_var = tk.BooleanVar(value=True)



        self._setup_window()

        self._build_ui()

        self._start_model_loading()



    def _setup_window(self) -> None:

        self.root.title("NLLB 本地翻译工具")

        self.root.geometry("800x640")

        self.root.minsize(560, 480)



    def _build_ui(self) -> None:

        main_frame = ttk.Frame(self.root, padding=12)

        main_frame.pack(fill=tk.BOTH, expand=True)



        self.input_label = ttk.Label(main_frame, text="输入 Input（中/英自动识别）")

        self.input_label.pack(anchor=tk.W)



        input_frame = ttk.Frame(main_frame)

        input_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 8))



        self.input_box = tk.Text(input_frame, wrap=tk.WORD, height=8, font=("Microsoft YaHei UI", 11))

        input_scroll = ttk.Scrollbar(input_frame, orient=tk.VERTICAL, command=self.input_box.yview)

        self.input_box.configure(yscrollcommand=input_scroll.set)

        self.input_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        input_scroll.pack(side=tk.RIGHT, fill=tk.Y)



        ctrl_frame = ttk.Frame(main_frame)

        ctrl_frame.pack(fill=tk.X, pady=(0, 4))



        ttk.Label(ctrl_frame, text="任务 Task:").pack(side=tk.LEFT)

        task_combo = ttk.Combobox(

            ctrl_frame,

            textvariable=self.task_var,

            values=[label for label, _ in self.TASK_OPTIONS],

            state="readonly",

            width=18,

        )

        task_combo.pack(side=tk.LEFT, padx=(4, 12))

        task_combo.bind("<<ComboboxSelected>>", self._on_task_changed)



        ttk.Label(ctrl_frame, text="路由 Mode:").pack(side=tk.LEFT)

        mode_combo = ttk.Combobox(

            ctrl_frame,

            textvariable=self.mode_var,

            values=[label for label, _ in self.MODE_OPTIONS],

            state="readonly",

            width=14,

        )

        mode_combo.pack(side=tk.LEFT, padx=(4, 12))



        ttk.Checkbutton(

            ctrl_frame,

            text="音频专业模式 Pro",

            variable=self.pro_mode_var,

        ).pack(side=tk.LEFT)



        self.task_hint_label = ttk.Label(

            main_frame,

            text=self.TASK_HINTS[TaskMode.FXNAME],

            wraplength=760,

            foreground="#555555",

        )

        self.task_hint_label.pack(anchor=tk.W, pady=(0, 8))



        btn_frame = ttk.Frame(main_frame)

        btn_frame.pack(fill=tk.X, pady=4)



        self.translate_btn = ttk.Button(

            btn_frame,

            text="Translate / 翻译",

            command=self._on_translate_click,

            state=tk.DISABLED,

        )

        self.translate_btn.pack(side=tk.LEFT)



        self.copy_btn = ttk.Button(

            btn_frame,

            text="Copy Result / 复制结果",

            command=self._on_copy_click,

            state=tk.DISABLED,

        )

        self.copy_btn.pack(side=tk.LEFT, padx=(8, 0))



        self.output_label = ttk.Label(main_frame, text="输出 Output")

        self.output_label.pack(anchor=tk.W)



        output_frame = ttk.Frame(main_frame)

        output_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 8))



        self.output_box = tk.Text(

            output_frame,

            wrap=tk.WORD,

            height=12,

            font=("Segoe UI", 11),

            state=tk.DISABLED,

        )

        output_scroll = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.output_box.yview)

        self.output_box.configure(yscrollcommand=output_scroll.set)

        self.output_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        output_scroll.pack(side=tk.RIGHT, fill=tk.Y)



        self.status_label = ttk.Label(main_frame, text="正在加载本地模型...", anchor=tk.W)

        self.status_label.pack(fill=tk.X, pady=(4, 0))



        self._last_output_text = ""



    def _on_task_changed(self, _event: object | None = None) -> None:

        task = self._get_selected_task()

        self.task_hint_label.config(text=self.TASK_HINTS.get(task, ""))



    def _get_selected_mode(self) -> TranslateMode:

        label = self.mode_var.get()

        for opt_label, mode in self.MODE_OPTIONS:

            if opt_label == label:

                return mode

        return TranslateMode.AUTO



    def _get_selected_task(self) -> TaskMode:

        label = self.task_var.get()

        for opt_label, task in self.TASK_OPTIONS:

            if opt_label == label:

                return task

        return TaskMode.FXNAME



    @staticmethod

    def _format_quality_block(result: TranslationResult) -> str:

        debug = result.debug or {}

        quality = debug.get("quality")

        issues = debug.get("issues") or []



        if result.task_mode == TaskMode.GENERAL.value:

            lines = [

                "",

                "Quality / 质量:",

                "General mode（无 FXName 质量门禁）",

                "",

                "Issues / 问题:",

                "None",

            ]

            return "\n".join(lines)



        if not result.text.strip():

            quality = "needs_review"

            if not issues:

                issues = ["empty_output"]



        if quality == "pass":

            quality_line = "Pass"

        elif quality == "fail":

            quality_line = "Needs Review / 需检查"

        elif quality == "needs_review":

            quality_line = "Needs Review / 需检查"

        else:

            quality_line = "—"



        issue_lines: list[str] = []

        has_rejected = False

        for issue in issues:

            if issue.startswith("rejected_nllb_candidate:"):

                has_rejected = True

                frag = issue.split(":", 1)[1].strip()

                issue_lines.append(f"Rejected NLLB phrase / 已拒绝 NLLB 脏短语: {frag}")

            elif issue.startswith("unknown_zh:"):

                issue_lines.append(f"unknown_zh: {issue.split(':', 1)[1].strip()}")

            elif issue in {"nllb_candidate_rejected", "nllb_rejected"}:

                has_rejected = True

                issue_lines.append("Rejected NLLB phrase / 已过滤脏短语")

            else:

                issue_lines.append(issue)

        for rej in debug.get("rejected_candidates") or []:

            has_rejected = True

            raw = rej.get("raw") or rej.get("sanitized") or ""

            if raw:

                issue_lines.append(f"Rejected NLLB phrase / 已拒绝 NLLB 脏短语: {raw}")

        if has_rejected and not any("已拒绝" in line or "已过滤" in line for line in issue_lines):

            issue_lines.append("Rejected NLLB phrase / 已过滤脏短语")



        if not issue_lines:

            issue_lines = ["None"]



        return "\n".join(

            [

                "",

                "Quality / 质量:",

                quality_line,

                "",

                "Issues / 问题:",

                *issue_lines,

            ]

        )



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

            self._set_status("模型与术语库已就绪 · 默认任务: FXName / 音效命名")



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

        task_mode = self._get_selected_task()

        pro_mode = self.pro_mode_var.get()



        def _worker() -> None:

            try:

                result = self.translator.translate(

                    input_text,

                    mode=mode,

                    pro_mode=pro_mode,

                    task_mode=task_mode,

                )

                self.root.after(0, lambda r=result: self._update_ui_success(r))

            except (TranslationError, Exception) as exc:

                self.root.after(0, lambda err=str(exc): self._update_ui_error(err))



        threading.Thread(target=_worker, daemon=True).start()



    def _update_ui_success(self, result: TranslationResult) -> None:

        display = f"Output:\n{result.text or '（空）'}"

        display += self._format_quality_block(result)

        self._last_output_text = result.text



        self.output_box.config(state=tk.NORMAL)

        self.output_box.delete("1.0", tk.END)

        self.output_box.insert("1.0", display)

        self.output_box.config(state=tk.DISABLED)



        self.copy_btn.config(state=tk.NORMAL if result.text.strip() else tk.DISABLED)

        self._set_status(f"翻译完成 ({result.status_label})")

        self.translate_btn.config(state=tk.NORMAL)



    def _update_ui_error(self, err_msg: str) -> None:

        self._set_status("翻译出错")

        self.translate_btn.config(state=tk.NORMAL)

        messagebox.showerror("错误", err_msg)



    def _on_copy_click(self) -> None:

        if not self._last_output_text.strip():

            return

        self.root.clipboard_clear()

        self.root.clipboard_append(self._last_output_text)

        self._set_status("已复制翻译结果到剪贴板")





def main() -> None:

    root = tk.Tk()

    TranslateApp(root)

    root.mainloop()





if __name__ == "__main__":

    main()

