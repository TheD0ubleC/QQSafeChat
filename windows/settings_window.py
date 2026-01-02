from __future__ import annotations
import tkinter as tk
from tkinter import font, messagebox, simpledialog

from storage.config import AppConfig
from storage.persona_store import PersonaStore
from storage.settings_store import SettingsStore
from windows.ui_theme import FONT_MONO, FONT_UI, apply_window_icon, ttk
import json
from core.llm_client import resolve_env, MockLLMClient, OpenAIClient


class SettingsWindow(tk.Toplevel):
    def __init__(
        self, master, store: SettingsStore, cfg: AppConfig, on_apply_llm, on_apply_cfg
    ):
        super().__init__(master)
        apply_window_icon(self)
        self.title("设置")
        self._apply_dpi_scaling()
        self._set_initial_geometry()
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.store = store
        self.cfg = cfg
        self.on_apply_llm = on_apply_llm
        self.on_apply_cfg = on_apply_cfg

        self.personas = PersonaStore(self.cfg.persona_dir)
        self.persona_dirty: dict[str, bool] = {}
        self._persona_current_name: str = ""
        self._persona_original_text: str = ""

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        nb = ttk.Notebook(root)
        nb.grid(row=0, column=0, sticky="nsew")
        self.nb = nb

        self.tab_llm = ttk.Frame(nb, padding=10)
        self.tab_behavior = ttk.Frame(nb, padding=10)
        self.tab_persona = ttk.Frame(nb, padding=10)
        self.tab_prompt = ttk.Frame(nb, padding=10)

        nb.add(self.tab_llm, text="LLM")
        nb.add(self.tab_behavior, text="行为")
        nb.add(self.tab_persona, text="人格")
        nb.add(self.tab_prompt, text="Prompt 预览")

        self._build_llm_tab()
        self._build_behavior_tab()
        self._build_persona_tab()
        self._build_prompt_tab()

        nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        side = ttk.Frame(root)
        side.grid(row=0, column=1, sticky="ns", padx=(12, 0))
        side.columnconfigure(0, weight=1)
        ttk.Button(side, text="保存并应用", command=self.save_apply).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(side, text="取消", command=self._on_close).grid(
            row=1, column=0, sticky="ew", pady=(8, 0)
        )

    def _apply_dpi_scaling(self):
        try:
            pixels_per_inch = self.winfo_fpixels("1i")
            scaling = pixels_per_inch / 72.0
            scaling = max(0.8, min(2.5, scaling))
            current = float(self.tk.call("tk", "scaling"))
            if abs(current - scaling) > 0.1:
                self.tk.call("tk", "scaling", scaling)
        except Exception:  # noqa: BLE001
            pass

    def _set_initial_geometry(self):
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(1280, int(screen_w * 0.9))
        height = min(820, int(screen_h * 0.85))
        if width < 900:
            width = min(900, screen_w)
        if height < 600:
            height = min(600, screen_h)
        if width < height:
            width = min(screen_w, max(width, int(height * 1.2)))
        self.geometry(f"{width}x{height}")
        try:
            self.minsize(820, 560)
        except Exception:  # noqa: BLE001
            pass

    def _build_llm_tab(self):
        frm = self.tab_llm

        tip = (
            "提示：任意输入以 $ 开头（例如 $OPENAI_API_KEY），将从环境变量读取。\n"
            "User Template 支持 {history} 和 {incoming} 两个占位符。"
        )
        ttk.Label(frm, text=tip).pack(anchor="w", pady=(0, 10))

        row0 = ttk.Frame(frm)
        row0.pack(fill="x", pady=4)
        ttk.Label(row0, text="Provider").pack(side="left", padx=(0, 8))
        self.provider_var = tk.StringVar(value=self.store.settings.provider)
        provider = ttk.Combobox(
            row0,
            textvariable=self.provider_var,
            values=["mock", "openai", "siliconflow"],
            width=12,
            state="readonly",
        )
        provider.pack(side="left")

        self.api_key_var = tk.StringVar(value=self.store.settings.api_key)
        self.base_url_var = tk.StringVar(value=self.store.settings.base_url)
        self.model_var = tk.StringVar(value=self.store.settings.model)
        self.temp_var = tk.StringVar(value=str(self.store.settings.temperature))

        self._labeled_entry(frm, "API Key", self.api_key_var)
        self._labeled_entry(frm, "Base URL", self.base_url_var)
        self._labeled_entry(frm, "Model", self.model_var)

        rowT = ttk.Frame(frm)
        rowT.pack(fill="x", pady=4)
        ttk.Label(rowT, text="Temperature").pack(side="left", padx=(0, 8))
        ttk.Entry(rowT, textvariable=self.temp_var, width=10).pack(side="left")
        ttk.Label(rowT, text="（0~2，一般 0.4~0.9）").pack(side="left", padx=8)

        ttk.Label(frm, text="System Prompt").pack(anchor="w", pady=(12, 4))
        self.system_text = tk.Text(frm, height=6, wrap="word", font=FONT_UI)
        self.system_text.pack(fill="x")
        self.system_text.insert("1.0", self.store.settings.system_prompt)

        ttk.Label(frm, text="User Template").pack(anchor="w", pady=(12, 4))
        self.user_text = tk.Text(frm, height=12, wrap="word", font=FONT_UI)
        self.user_text.pack(fill="both", expand=True)
        self.user_text.insert("1.0", self.store.settings.user_template)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="填充示例模板", command=self.fill_example).pack(
            side="right"
        )

    def _labeled_entry(self, parent, label, var):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=12).pack(side="left", padx=(0, 8))
        ent = ttk.Entry(row, textvariable=var)
        ent.pack(side="left", fill="x", expand=True)

    def fill_example(self):
        self.system_text.delete("1.0", tk.END)
        self.system_text.insert("1.0", "你是一个友好、自然、简洁的聊天助手。")

        example = (
            "你是一个聊天助手。下面是聊天上下文（可能包含多行文件信息，已经合并成一个气泡）。\n"
            "请你只对“对方”最新消息进行简短自然回复，不要复述上下文。\n\n"
            "【聊天上下文】\n"
            "{history}\n\n"
            "【对方最新消息】\n"
            "{incoming}\n\n"
            "【你的回复】"
        )
        self.user_text.delete("1.0", tk.END)
        self.user_text.insert("1.0", example)
        self.refresh_prompt_preview()

    def _build_behavior_tab(self):
        frm = self.tab_behavior

        box = ttk.Labelframe(frm, text="停发后回复延迟", padding=10)
        box.pack(fill="x")

        self.reply_stop_var = tk.StringVar(value=str(self.cfg.reply_stop_seconds))
        self.delay_mode_var = tk.StringVar(
            value=self.cfg.reply_delay_mode or "fixed+random"
        )
        self.rand_min_var = tk.StringVar(value=str(self.cfg.reply_random_min))
        self.rand_max_var = tk.StringVar(value=str(self.cfg.reply_random_max))

        row1 = ttk.Frame(box)
        row1.pack(fill="x", pady=4)
        ttk.Label(row1, text="基础等待（秒）", width=14).pack(side="left")
        ttk.Entry(row1, textvariable=self.reply_stop_var, width=10).pack(side="left")
        ttk.Label(row1, text="对方最后一条消息后至少等这么久").pack(side="left", padx=8)

        row2 = ttk.Frame(box)
        row2.pack(fill="x", pady=6)
        ttk.Label(row2, text="模式", width=14).pack(side="left")
        ttk.Radiobutton(
            row2,
            text="固定",
            value="fixed",
            variable=self.delay_mode_var,
            command=self._refresh_delay_mode,
        ).pack(side="left")
        ttk.Radiobutton(
            row2,
            text="固定 + 随机",
            value="fixed+random",
            variable=self.delay_mode_var,
            command=self._refresh_delay_mode,
        ).pack(side="left", padx=10)

        row3 = ttk.Frame(box)
        row3.pack(fill="x", pady=4)
        ttk.Label(row3, text="随机最小/最大", width=14).pack(side="left")
        self.rand_min_ent = ttk.Entry(row3, textvariable=self.rand_min_var, width=10)
        self.rand_max_ent = ttk.Entry(row3, textvariable=self.rand_max_var, width=10)
        self.rand_min_ent.pack(side="left")
        ttk.Label(row3, text="~").pack(side="left", padx=6)
        self.rand_max_ent.pack(side="left")
        ttk.Label(row3, text="秒（在基础等待后额外加）").pack(side="left", padx=8)

        self._refresh_delay_mode()

        box2 = ttk.Labelframe(frm, text="分割消息发送速度", padding=10)
        box2.pack(fill="x", pady=(10, 0))

        self.split_delim_var = tk.StringVar(value=self.cfg.split_delimiter)
        self.speed_mult_var = tk.StringVar(value=str(self.cfg.split_speed_multiplier))

        rowa = ttk.Frame(box2)
        rowa.pack(fill="x", pady=4)
        ttk.Label(rowa, text="分隔符", width=14).pack(side="left")
        ttk.Entry(rowa, textvariable=self.split_delim_var, width=18).pack(side="left")
        ttk.Label(rowa, text="AI 用它把回复拆成多条").pack(side="left", padx=8)

        rowb = ttk.Frame(box2)
        rowb.pack(fill="x", pady=4)
        ttk.Label(rowb, text="速度倍率", width=14).pack(side="left")
        ttk.Entry(rowb, textvariable=self.speed_mult_var, width=10).pack(side="left")
        ttk.Label(rowb, text="1.0=正常；2.0更快；0.5更慢（影响分割消息之间间隔）").pack(
            side="left", padx=8
        )

    def _refresh_delay_mode(self):
        mode = (self.delay_mode_var.get() or "fixed").strip().lower()
        enabled = mode != "fixed"
        state = "normal" if enabled else "disabled"
        try:
            self.rand_min_ent.configure(state=state)
            self.rand_max_ent.configure(state=state)
        except Exception:  # noqa: BLE001
            pass

    def _build_persona_tab(self):
        frm = self.tab_persona

        top = ttk.Frame(frm)
        top.pack(fill="x")
        ttk.Label(top, text=f"人格文件夹：{self.cfg.persona_dir}").pack(side="left")
        ttk.Button(
            top, text="刷新", command=lambda: self._persona_refresh(check_dirty=True)
        ).pack(side="right")
        ttk.Button(top, text="新建", command=self._persona_create).pack(
            side="right", padx=6
        )

        mid = ttk.Frame(frm)
        mid.pack(fill="both", expand=True, pady=(10, 0))

        left = ttk.Frame(mid)
        left.pack(side="left", fill="y")

        right = ttk.Frame(mid)
        right.pack(side="right", fill="both", expand=True, padx=(10, 0))

        ttk.Label(left, text="文件列表").pack(anchor="w")
        self.persona_list = tk.Listbox(left, height=18, width=28, exportselection=False)
        self.persona_list.pack(fill="y", expand=False)
        self.persona_list.bind("<<ListboxSelect>>", self._persona_on_select)
        self.persona_list_font = font.Font(
            root=self, font=self.persona_list.cget("font")
        )
        self.persona_list_font_bold = font.Font(root=self, font=self.persona_list_font)
        self.persona_list_font_bold.configure(weight="bold")

        self.persona_info = tk.StringVar(
            value=f"当前应用：{self.cfg.persona_file or '（无）'}"
        )
        ttk.Label(left, textvariable=self.persona_info).pack(anchor="w", pady=(8, 0))

        ttk.Button(
            left, text="应用选中人格", command=self._persona_apply_selected
        ).pack(fill="x", pady=(8, 0))
        ttk.Button(left, text="保存文件内容", command=self._persona_save_current).pack(
            fill="x", pady=6
        )
        ttk.Button(left, text="重命名", command=self._persona_rename).pack(
            fill="x", pady=6
        )
        ttk.Button(left, text="删除", command=self._persona_delete).pack(
            fill="x", pady=6
        )

        ttk.Label(right, text="内容预览 / 编辑").pack(anchor="w")
        text_frame = ttk.Frame(right)
        text_frame.pack(fill="both", expand=True)
        self.persona_text_font = font.Font(root=self, font=FONT_UI)
        self.persona_text = tk.Text(
            text_frame, wrap="word", font=self.persona_text_font
        )
        self.persona_text.pack(side="left", fill="both", expand=True)
        persona_scroll = ttk.Scrollbar(
            text_frame, orient="vertical", command=self.persona_text.yview
        )
        persona_scroll.pack(side="right", fill="y")
        self.persona_text.configure(yscrollcommand=persona_scroll.set)
        self.persona_text.bind("<<Modified>>", self._on_persona_modified)
        for seq in ("<Control-MouseWheel>", "<Control-Button-4>", "<Control-Button-5>"):
            self.persona_text.bind(seq, self._on_persona_zoom)

        self._persona_refresh(select=self.cfg.persona_file)

    def _build_prompt_tab(self):
        frm = self.tab_prompt

        info = (
            "Prompt 预览：\n"
            "- Persona 使用“当前应用”的人格（也就是左侧显示的 当前应用：xxx），而不是右侧编辑框的未保存内容。\n"
            "- 下面的“模拟聊天记录”会用于替换 {history}/{incoming}。\n"
            "- 预览仍支持 $ENV_VAR 解析；System 为空会用默认 'You are a helpful assistant.'。\n"
        )
        ttk.Label(frm, text=info, wraplength=760).pack(anchor="w")

        sim = ttk.Labelframe(
            frm, text="模拟聊天记录（用于 {history}/{incoming}）", padding=8
        )
        sim.pack(fill="x", pady=(0, 8))

        self._preview_history_sample = (
            "[对方] 测试消息1\n[对方] 测试消息2\n[自己] 测试消息3\n[自己] 测试消息4"
        )
        self._preview_incoming_sample = "[对方] 测试消息5"

        ttk.Label(sim, text="history（{history}）").pack(anchor="w")
        self.preview_history_text = tk.Text(sim, height=6, wrap="none", font=FONT_MONO)
        self.preview_history_text.pack(fill="x", pady=(2, 6))
        self.preview_history_text.insert("1.0", self._preview_history_sample)

        ttk.Label(sim, text="incoming（{incoming}）").pack(anchor="w")
        self.preview_incoming_text = tk.Text(sim, height=3, wrap="none", font=FONT_MONO)
        self.preview_incoming_text.pack(fill="x", pady=(2, 0))
        self.preview_incoming_text.insert("1.0", self._preview_incoming_sample)

        def _reset_samples():
            try:
                self.preview_history_text.delete("1.0", tk.END)
                self.preview_history_text.insert("1.0", self._preview_history_sample)
                self.preview_incoming_text.delete("1.0", tk.END)
                self.preview_incoming_text.insert("1.0", self._preview_incoming_sample)
            except Exception:
                pass
            self.refresh_prompt_preview()

        btns_right = ttk.Frame(sim)
        btns_right.pack(fill="x")
        ttk.Button(btns_right, text="重置为默认示例", command=_reset_samples).pack(
            side="right", pady=(6, 0)
        )
        ttk.Button(
            btns_right, text="刷新预览", command=self.refresh_prompt_preview
        ).pack(side="right", padx=8, pady=(6, 0))
        self.preview_nb = ttk.Notebook(frm)
        self.preview_nb.pack(fill="both", expand=True)

        tab_sys = ttk.Frame(self.preview_nb, padding=6)
        tab_user = ttk.Frame(self.preview_nb, padding=6)
        tab_payload = ttk.Frame(self.preview_nb, padding=6)

        self.preview_nb.add(tab_sys, text="System（最终）")
        self.preview_nb.add(tab_user, text="User（最终）")
        self.preview_nb.add(tab_payload, text="Payload（OpenAI）")

        self.prompt_preview_system = self._make_preview_text(tab_sys)
        self.prompt_preview_user = self._make_preview_text(tab_user)
        self.prompt_preview_payload = self._make_preview_text(tab_payload)

        self.refresh_prompt_preview()

    def _on_tab_changed(self, event):
        tab_id = event.widget.select()
        if tab_id == str(self.tab_prompt):
            self.refresh_prompt_preview()
        elif tab_id == str(self.tab_persona):
            self._persona_ensure_selection()

    def _build_split_rules(self, split_delimiter: str) -> str:
        d = (split_delimiter or "").strip()
        if not d:
            return ""
        return (
            "【输出格式规则】\n"
            "- 你的最终输出只能是“回复文本”，不要加前缀/解释/markdown。\n"
            "- 你可以输出 1 条或多条消息。\n"
            f"- 如果输出多条消息：必须用分隔符 {d} 分隔各条消息。\n"
            "- 分隔符不要出现在开头或结尾。\n"
            f"- 示例：你好{d}最近咋样？\n"
        )

    def _get_applied_persona_text(self) -> str:
        name = (self.cfg.persona_file or "").strip()
        if not name:
            return ""
        try:
            return (self.personas.read(name) or "").strip()
        except Exception:
            return ""

    def refresh_prompt_preview(self):
        system_prompt_raw = self.system_text.get("1.0", tk.END).rstrip("\n")
        user_template_raw = self.user_text.get("1.0", tk.END).rstrip("\n")

        system_prompt = resolve_env(system_prompt_raw).strip()
        user_template = resolve_env(user_template_raw).strip() or "{incoming}"

        split_delimiter = (
            self.split_delim_var.get() or "<<<NEXT>>>"
        ).strip() or "<<<NEXT>>>"
        split_rules = self._build_split_rules(split_delimiter)

        persona = self._get_applied_persona_text()

        try:
            history_text = self.preview_history_text.get("1.0", tk.END).rstrip("\n")
            incoming_text = self.preview_incoming_text.get("1.0", tk.END).rstrip("\n")
        except Exception:
            history_text = self._preview_history_sample
            incoming_text = self._preview_incoming_sample

        sticker_enabled = bool(getattr(self.cfg, "sticker_selector_enabled", False))
        sticker_prompt = (
            getattr(self.cfg, "sticker_selector_prompt", "") or ""
        ).strip()

        sys_parts = [system_prompt or "You are a helpful assistant."]

        if persona:
            sys_parts.append("【人格设定】\n" + persona)

        if sticker_enabled and sticker_prompt:
            sys_parts.append("【表情包提示】\n" + sticker_prompt)

        if split_rules:
            sys_parts.append(split_rules)

        system_final = "\n\n".join(sys_parts)

        try:
            user_prompt = user_template.format(
                history=history_text,
                incoming=incoming_text,
            )
        except Exception as exc:  # noqa: BLE001
            user_prompt = f"（User Template 格式化失败：{exc}）"

        if split_rules and not user_prompt.startswith("（User Template 格式化失败"):
            user_prompt = user_prompt + "\n\n【再次强调输出格式】\n" + split_rules

        model = resolve_env(self.model_var.get() or "").strip()
        try:
            temperature = float((self.temp_var.get() or "").strip())
        except Exception:
            temperature = self.store.settings.temperature

        payload = {
            "model": model or "(empty model)",
            "messages": [
                {"role": "system", "content": system_final},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        self._set_prompt_preview_text(self.prompt_preview_system, system_final)
        self._set_prompt_preview_text(self.prompt_preview_user, user_prompt)
        self._set_prompt_preview_text(
            self.prompt_preview_payload,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )

    def _make_preview_client(self):
        provider = (self.provider_var.get() or "mock").strip().lower()

        api_key = self.api_key_var.get()
        base_url = self.base_url_var.get()
        model = self.model_var.get()

        try:
            temperature = float((self.temp_var.get() or "").strip())
        except Exception:
            temperature = float(self.store.settings.temperature or 0.7)

        system_prompt = self.system_text.get("1.0", tk.END).rstrip("\n")
        user_template = self.user_text.get("1.0", tk.END).rstrip("\n")

        if provider == "openai":
            return OpenAIClient(
                api_key=api_key,
                base_url=base_url,
                model=model,
                temperature=temperature,
                system_prompt=system_prompt,
                user_template=user_template,
            )
        return MockLLMClient()

    def _make_preview_text(self, parent) -> tk.Text:
        wrap = "none"  # 关键：别 wrap，避免看起来“换行错了”
        frm = ttk.Frame(parent)
        frm.pack(fill="both", expand=True)

        yscroll = ttk.Scrollbar(frm, orient="vertical")
        yscroll.pack(side="right", fill="y")

        xscroll = ttk.Scrollbar(frm, orient="horizontal")
        xscroll.pack(side="bottom", fill="x")

        txt = tk.Text(frm, wrap=wrap, font=FONT_MONO, state="disabled")
        txt.pack(side="left", fill="both", expand=True)

        txt.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.configure(command=txt.yview)
        xscroll.configure(command=txt.xview)
        return txt

    def _set_prompt_preview_text(self, widget: tk.Text, text: str):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text or "")
        widget.configure(state="disabled")

    def _persona_refresh(self, select: str = "", check_dirty: bool = False):
        if (
            check_dirty
            and self._persona_current_name
            and self.persona_dirty.get(self._persona_current_name)
        ):
            decision = self._confirm_unsaved_change("refresh")
            if decision == "cancel":
                return
            if decision == "save" and not self._persona_save_current(
                show_message=False
            ):
                return

        current = self._persona_current_name
        self.persona_list.delete(0, tk.END)
        files = self.personas.list_files()
        for f in files:
            self.persona_list.insert(tk.END, f)
            self._persona_set_dirty(f, self.persona_dirty.get(f, False))

        target = select if select in files else ""
        if not target and current in files:
            target = current
        if not target and self.cfg.persona_file in files:
            target = self.cfg.persona_file
        if not target and files:
            target = files[0]

        if target:
            self._persona_select_name(target)
            self._persona_load_content(target)
        else:
            self._persona_current_name = ""
            self.persona_text.delete("1.0", tk.END)

    def _persona_selected_name(self) -> str:
        sel = self.persona_list.curselection()
        if not sel:
            return ""
        return self.persona_list.get(sel[0])

    def _persona_index(self, name: str) -> int | None:
        try:
            files = list(self.persona_list.get(0, tk.END))
            if name in files:
                return files.index(name)
        except Exception:  # noqa: BLE001
            return None
        return None

    def _persona_select_name(self, name: str):
        idx = self._persona_index(name)
        if idx is None:
            return
        self.persona_list.selection_clear(0, tk.END)
        self.persona_list.selection_set(idx)
        self.persona_list.see(idx)

    def _persona_on_select(self, _=None):
        target = self._persona_selected_name()
        if not target or target == self._persona_current_name:
            return

        decision = self._confirm_unsaved_change("switch", target)
        if decision == "cancel":
            self._persona_select_name(self._persona_current_name)
            return
        if decision == "save" and not self._persona_save_current(show_message=False):
            self._persona_select_name(self._persona_current_name)
            return

        self._persona_load_content(target)

    def _confirm_unsaved_change(self, action: str, target: str | None = None) -> str:
        if not self._persona_current_name or not self.persona_dirty.get(
            self._persona_current_name
        ):
            return "proceed"

        if action == "switch" and target:
            action_text = f"切换到 {target}"
        elif action == "exit":
            action_text = "退出"
        elif action == "refresh":
            action_text = "刷新列表"
        else:
            action_text = "继续"

        res = messagebox.askyesnocancel(
            "未保存的更改",
            (
                f"人格文件“{self._persona_current_name}”已修改但未保存，是否保存后{action_text}？\n"
                "选择“否”将放弃更改继续，取消则留在当前文件。"
            ),
            parent=self,
        )
        if res is None:
            return "cancel"
        return "save" if res else "discard"

    def _persona_load_content(self, name: str):
        content = self.personas.read(name)
        self._persona_current_name = name
        self.persona_text.delete("1.0", tk.END)
        self.persona_text.insert("1.0", content)
        self.persona_text.edit_modified(False)
        self._persona_original_text = (content or "").rstrip("\n")
        self._persona_set_dirty(name, False)

    def _persona_set_dirty(self, name: str, dirty: bool):
        if not name:
            return
        self.persona_dirty[name] = dirty
        idx = self._persona_index(name)
        if idx is None:
            return
        font_to_use = self.persona_list_font_bold if dirty else self.persona_list_font
        try:
            self.persona_list.itemconfig(idx, font=font_to_use)
        except Exception:  # noqa: BLE001
            pass

    def _on_persona_modified(self, _=None):
        if not self.persona_text.edit_modified():
            return
        self.persona_text.edit_modified(False)
        if not self._persona_current_name:
            return
        current_text = self.persona_text.get("1.0", tk.END).rstrip("\n")
        self._persona_set_dirty(
            self._persona_current_name,
            current_text != (self._persona_original_text or ""),
        )

    def _persona_save_current(self, show_message: bool = True) -> bool:
        name = self._persona_current_name or self._persona_selected_name()
        if not name:
            if show_message:
                messagebox.showinfo("提示", "请先选中一个人格文件")
            return False
        ok = self._persona_save_by_name(name)
        if ok and show_message:
            messagebox.showinfo("成功", f"已保存：{name}")
        elif not ok and show_message:
            messagebox.showerror("失败", "保存失败（文件权限/路径问题）")
        return ok

    def _persona_save_by_name(self, name: str) -> bool:
        content = self.persona_text.get("1.0", tk.END).rstrip("\n")
        ok = self.personas.write(name, content)
        if ok:
            self._persona_original_text = content
            self._persona_set_dirty(name, False)
        return ok

    def _persona_apply_selected(self):
        name = self._persona_selected_name()
        if not name:
            messagebox.showinfo("提示", "请先选中一个人格文件")
            return
        self.cfg.persona_file = name
        self.persona_info.set(f"当前应用：{self.cfg.persona_file}")
        messagebox.showinfo("已应用", f"已选择人格：{name}")

        try:
            if str(self.nb.select()) == str(self.tab_prompt):
                self.refresh_prompt_preview()
        except Exception:
            pass

    def _persona_create(self):
        name = simpledialog.askstring(
            "新建人格", "输入文件名（例如 cute.txt / calm.md）", parent=self
        )
        if not name:
            return
        ok = self.personas.create(
            name, "（在这里写人格设定：口吻、习惯、禁忌、称呼方式等）\n"
        )
        if not ok:
            messagebox.showerror("失败", "创建失败（可能已存在/文件名非法）")
            return
        self._persona_refresh(select=name, check_dirty=True)

    def _persona_rename(self):
        current_name = self._persona_selected_name()
        if not current_name:
            messagebox.showinfo("提示", "请先选中一个人格文件")
            return
        
        new_name = simpledialog.askstring(
            "重命名人格", 
            f"将 {current_name} 重命名为：", 
            initialvalue=current_name,
            parent=self
        )
        if not new_name or new_name == current_name:
            return
        
        ok = self.personas.rename(current_name, new_name)
        if ok:
            # 更新当前应用的人格文件名称（如果重命名的是当前应用的文件）
            if self.cfg.persona_file == current_name:
                self.cfg.persona_file = new_name
                self.persona_info.set(f"当前应用：{self.cfg.persona_file}")
            self._persona_refresh(select=new_name, check_dirty=True)
            messagebox.showinfo("成功", f"已重命名：{current_name} → {new_name}")
        else:
            messagebox.showerror("失败", "重命名失败（可能目标文件已存在或文件名非法）")
    
    def _persona_delete(self):
        current_name = self._persona_selected_name()
        if not current_name:
            messagebox.showinfo("提示", "请先选中一个人格文件")
            return
        
        if current_name == self.cfg.persona_file:
            messagebox.showerror("错误", "不能删除当前正在使用的人格文件")
            return
        
        confirmed = messagebox.askyesno(
            "确认删除", 
            f"确定要删除人格文件 {current_name} 吗？此操作不可恢复。",
            parent=self
        )
        if confirmed:
            ok = self.personas.delete(current_name)
            if ok:
                self._persona_refresh(check_dirty=True)
                messagebox.showinfo("成功", f"已删除：{current_name}")
            else:
                messagebox.showerror("失败", "删除失败（可能文件不存在或被占用）")
    
    def _on_persona_zoom(self, event):
        delta = 0
        if getattr(event, "delta", 0) != 0:
            delta = 1 if event.delta > 0 else -1
        elif getattr(event, "num", None) in (4, 5):
            delta = 1 if event.num == 4 else -1
        if delta == 0:
            return "break"
        current_size = int(self.persona_text_font.cget("size"))
        new_size = max(6, min(48, current_size + delta))
        self.persona_text_font.configure(size=new_size)
        return "break"

    def _persona_ensure_selection(self):
        if self._persona_selected_name():
            return
        preferred = self.cfg.persona_file or self._persona_current_name
        if preferred:
            self._persona_select_name(preferred)
            self._persona_load_content(preferred)
        elif self.persona_list.size() > 0:
            name = self.persona_list.get(0)
            self._persona_select_name(name)
            self._persona_load_content(name)

    def _on_close(self):
        decision = self._confirm_unsaved_change("exit")
        if decision == "cancel":
            return
        if decision == "save" and not self._persona_save_current(show_message=True):
            return
        self.destroy()

    def save_apply(self):
        decision = self._confirm_unsaved_change("exit")
        if decision == "cancel":
            return
        if decision == "save" and not self._persona_save_current(show_message=True):
            return

        s = self.store.settings
        s.provider = self.provider_var.get().strip() or "mock"
        s.api_key = self.api_key_var.get().strip()
        s.base_url = self.base_url_var.get().strip()
        s.model = self.model_var.get().strip()
        s.system_prompt = self.system_text.get("1.0", tk.END).rstrip("\n")
        s.user_template = self.user_text.get("1.0", tk.END).rstrip("\n")
        try:
            s.temperature = float(self.temp_var.get().strip())
        except Exception:  # noqa: BLE001
            messagebox.showerror("错误", "Temperature 不是数字")
            return

        try:
            self.cfg.reply_stop_seconds = float(self.reply_stop_var.get().strip())
        except Exception:  # noqa: BLE001
            messagebox.showerror("错误", "基础等待（秒）不是数字")
            return

        self.cfg.reply_delay_mode = (self.delay_mode_var.get() or "fixed").strip()

        try:
            self.cfg.reply_random_min = float(self.rand_min_var.get().strip())
            self.cfg.reply_random_max = float(self.rand_max_var.get().strip())
        except Exception:  # noqa: BLE001
            messagebox.showerror("错误", "随机最小/最大不是数字")
            return

        self.cfg.split_delimiter = (
            self.split_delim_var.get() or "<<<NEXT>>>"
        ).strip() or "<<<NEXT>>>"
        try:
            self.cfg.split_speed_multiplier = float(self.speed_mult_var.get().strip())
        except Exception:  # noqa: BLE001
            messagebox.showerror("错误", "速度倍率不是数字")
            return

        self.store.save()
        self.cfg.save(self.cfg.config_path)

        self.on_apply_llm(s)
        self.on_apply_cfg(self.cfg)

        self.destroy()
