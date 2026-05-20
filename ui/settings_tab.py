import os
import subprocess

import customtkinter as ctk
from core.paths import DB_PATH, DATA_ROOT
from db import reset_password, get_all_users, delete_user, create_user, get_setting, save_setting
from ui.theme import (
    BG, BG_ALT, BG_DEEP, PAPER, TEXT, TEXT_MUTED, TEXT_GHOST,
    BORDER, BORDER_W, BORDER_SOFT, ACCENT, ACCENT_SOFT,
    font, styled_entry, section_label, divider,
    primary_btn, secondary_btn, card_frame, option_menu, scrollable,
)


# ── Dialogs ───────────────────────────────────────────────────────────────────

class ChangePasswordDialog(ctk.CTkToplevel):
    def __init__(self, parent, username: str):
        super().__init__(parent)
        self.username = username
        self.title("Смена пароля")
        self.geometry("400x360")
        self.minsize(360, 320)
        self.resizable(True, True)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.configure(fg_color=BG)
        self._build()
        self.bind("<Return>", lambda _: self._on_save())

    def _build(self):
        # Grid: top spacer / content / spacer / buttons
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)
        self.grid_columnconfigure(0, weight=1)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="ew", padx=24, pady=(8, 20))
        secondary_btn(btn_row, "Отмена", command=self.destroy).pack(
            side="left", expand=True, fill="x", padx=(0, 6))
        primary_btn(btn_row, "Готово", command=self._on_save).pack(
            side="left", expand=True, fill="x", padx=(6, 0))

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=1, column=0, sticky="ew", padx=24)

        ctk.CTkLabel(center, text="Смена пароля",
                     font=font(16, "bold"), text_color=TEXT).pack(pady=(0, 4))
        ctk.CTkLabel(center, text=f"Пользователь: {self.username}",
                     font=font(12), text_color=TEXT_MUTED).pack(pady=(0, 12))

        card = card_frame(center)
        card.pack(fill="x")

        ctk.CTkLabel(card, text="НОВЫЙ ПАРОЛЬ", font=font(10, "bold"),
                     text_color=TEXT_GHOST, anchor="w").pack(
                         anchor="w", padx=16, pady=(16, 3))
        self.new_pass = styled_entry(card, "Введите новый пароль", show="•")
        self.new_pass.pack(padx=16, fill="x")

        ctk.CTkLabel(card, text="ПОДТВЕРЖДЕНИЕ", font=font(10, "bold"),
                     text_color=TEXT_GHOST, anchor="w").pack(
                         anchor="w", padx=16, pady=(10, 3))
        self.confirm_pass = styled_entry(card, "Повторите пароль", show="•")
        self.confirm_pass.pack(padx=16, fill="x")

        self.error_label = ctk.CTkLabel(card, text="",
                                         text_color="#cc3333", font=font(12))
        self.error_label.pack(pady=(6, 12))

    def _on_save(self):
        new, confirm = self.new_pass.get(), self.confirm_pass.get()
        if not new:
            self.error_label.configure(text="Введите новый пароль"); return
        if len(new) < 4:
            self.error_label.configure(text="Пароль минимум 4 символа"); return
        if new != confirm:
            self.error_label.configure(text="Пароли не совпадают")
            self.confirm_pass.delete(0, "end"); self.confirm_pass.focus(); return
        ok = reset_password(self.username, new)
        if ok:
            self.destroy()
        else:
            self.error_label.configure(text="Ошибка: пользователь не найден")


class AddUserDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_created):
        super().__init__(parent)
        self.on_created = on_created
        self.title("Добавить пользователя")
        self.geometry("400x300")
        self.minsize(340, 260)
        self.resizable(True, True)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.configure(fg_color=BG)
        self._build()
        self.bind("<Return>", lambda _: self._on_add())

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)
        self.grid_columnconfigure(0, weight=1)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="ew", padx=24, pady=(8, 20))
        secondary_btn(btn_row, "Отмена", command=self.destroy).pack(
            side="left", expand=True, fill="x", padx=(0, 6))
        primary_btn(btn_row, "Создать", command=self._on_add).pack(
            side="left", expand=True, fill="x", padx=(6, 0))

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=1, column=0, sticky="ew", padx=24)

        ctk.CTkLabel(center, text="Новый пользователь",
                     font=font(16, "bold"), text_color=TEXT).pack(pady=(0, 4))
        ctk.CTkLabel(center,
                     text="Пароль будет задан при первом входе.",
                     font=font(12), text_color=TEXT_MUTED).pack(pady=(0, 12))

        card = card_frame(center)
        card.pack(fill="x")

        ctk.CTkLabel(card, text="ЛОГИН", font=font(10, "bold"),
                     text_color=TEXT_GHOST, anchor="w").pack(
                         anchor="w", padx=16, pady=(16, 3))
        self.username_entry = styled_entry(card, "Введите логин")
        self.username_entry.pack(padx=16, fill="x")

        self._is_admin_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            card,
            text="Права администратора",
            variable=self._is_admin_var,
            font=font(12),
            text_color=TEXT_MUTED,
            checkmark_color=ACCENT_SOFT,
            fg_color=ACCENT,
            hover_color=ACCENT_SOFT,
            border_color=BORDER_SOFT,
        ).pack(anchor="w", padx=16, pady=(12, 4))

        self.error_label = ctk.CTkLabel(card, text="",
                                         text_color="#cc3333", font=font(12))
        self.error_label.pack(pady=(4, 12))

    def _on_add(self):
        username = self.username_entry.get().strip()
        if not username:
            self.error_label.configure(text="Введите имя пользователя"); return
        try:
            create_user(username, is_admin=self._is_admin_var.get())
        except Exception:
            self.error_label.configure(text="Пользователь уже существует"); return
        self.on_created()
        self.destroy()


# ── Main tab ──────────────────────────────────────────────────────────────────

class SettingsTab(ctk.CTkFrame):
    def __init__(self, parent, current_user: dict):
        super().__init__(parent, fg_color="transparent")
        self.current_user = current_user
        self._section_frames: dict = {}
        self._section_btns:   dict = {}
        self._build()

    # ──────────────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Left navigation panel ──────────────────────────────────────────
        left = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=BG_ALT)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        ctk.CTkFrame(self, width=2, corner_radius=0,
                     fg_color=BORDER_SOFT).pack(side="left", fill="y")

        section_label(left, "Настройки", padx=16, pady=(16, 12))

        sections = [
            ("users",    "Пользователи"),
            ("llm",      "LLM (Ollama)"),
            ("api",      "eLibrary"),
            ("database", "База данных"),
        ]
        for key, label in sections:
            btn = ctk.CTkButton(
                left, text=label, height=36, corner_radius=3,
                anchor="w", font=font(13),
                fg_color="transparent", text_color=TEXT_MUTED,
                hover_color=BG_DEEP, border_width=0,
                command=lambda k=key: self._show_section(k),
            )
            btn.pack(padx=10, fill="x", pady=1)
            self._section_btns[key] = btn

        # Admin notice at bottom
        ctk.CTkFrame(left, fg_color="transparent").pack(expand=True, fill="both")
        ctk.CTkLabel(left, text="Раздел доступен\nтолько администраторам",
                     font=font(10), text_color=TEXT_GHOST,
                     justify="center").pack(padx=16, pady=12)

        # ── Right content area ─────────────────────────────────────────────
        right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Build each section frame, stacked in the same grid cell
        self._section_frames["users"]    = self._build_users(right)
        self._section_frames["llm"]      = self._build_llm(right)
        self._section_frames["api"]      = self._build_api(right)
        self._section_frames["database"] = self._build_database(right)

        for frame in self._section_frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

        self._show_section("users")

    # ── Section builders ───────────────────────────────────────────────────

    def _build_users(self, parent) -> ctk.CTkFrame:
        frame = scrollable(parent)

        # Header row
        hdr = ctk.CTkFrame(frame, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(20, 12))

        title_col = ctk.CTkFrame(hdr, fg_color="transparent")
        title_col.pack(side="left")
        ctk.CTkLabel(title_col, text="Управление пользователями",
                     font=font(18, "bold"), text_color=TEXT).pack(anchor="w")
        section_label(title_col, "Администрирование", pady=(2, 0))

        primary_btn(hdr, "＋  Добавить пользователя",
                    command=self._open_add_user,
                    height=38).pack(side="right")

        # Table header
        th = ctk.CTkFrame(frame, fg_color=BG_DEEP, corner_radius=3)
        th.pack(fill="x", padx=20, pady=(0, 2))
        for col_text, w in [("#", 32), ("Логин", 0), ("Роль", 100), ("Действия", 160)]:
            ctk.CTkLabel(th, text=col_text.upper(),
                         font=font(10, "bold"), text_color=TEXT_GHOST,
                         width=w if w else 0, anchor="w").pack(
                             side="left", padx=(12, 4), pady=8,
                             **({"fill": "x", "expand": True} if w == 0 else {}))

        # User rows container
        self._users_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._users_frame.pack(fill="x", padx=20, pady=(0, 20))
        self._refresh_users()

        return frame

    def _build_llm(self, parent) -> ctk.CTkFrame:
        frame = scrollable(parent)
        self._section_header(frame, "LLM (Ollama)", "Конфигурация модели")

        card = card_frame(frame)
        card.pack(fill="x", padx=20, pady=(0, 16))

        for lbl, ph in [("URL Ollama", "http://localhost:11434")]:
            self._cfg_row(card, lbl, ph)

        # Model + test
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkLabel(row, text="Модель", font=font(12),
                     text_color=TEXT_MUTED, width=140, anchor="w").pack(side="left")
        option_menu(row, ["qwen2.5:3b", "qwen2.5:1.5b", "qwen2.5:0.5b"],
                    width=180).pack(side="left", padx=(0, 8))
        secondary_btn(row, "Проверить", height=36).pack(side="left")

        # Temperature
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkLabel(row2, text="Температура", font=font(12),
                     text_color=TEXT_MUTED, width=140, anchor="w").pack(side="left")
        ctk.CTkSlider(row2, from_=0, to=1, number_of_steps=10,
                      fg_color=BG_DEEP, progress_color=ACCENT,
                      button_color=ACCENT,
                      button_hover_color="#c56844").pack(
                          side="left", fill="x", expand=True, padx=(0, 12))

        return frame

    def _build_api(self, parent) -> ctk.CTkFrame:
        frame = scrollable(parent)
        self._section_header(frame, "Учётные данные", "Доступ к eLibrary.ru (РИНЦ)")

        eli_card = card_frame(frame)
        eli_card.pack(fill="x", padx=20, pady=(0, 4))

        ctk.CTkLabel(eli_card,
                     text="Требуется бесплатный аккаунт на elibrary.ru",
                     font=font(11), text_color=TEXT_GHOST, anchor="w").pack(
                         anchor="w", padx=16, pady=(12, 6))

        row_login = ctk.CTkFrame(eli_card, fg_color="transparent")
        row_login.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(row_login, text="Логин", font=font(12),
                     text_color=TEXT_MUTED, width=110, anchor="w").pack(side="left")
        self._eli_login = styled_entry(row_login, "email или логин", height=36)
        self._eli_login.pack(side="left", fill="x", expand=True)
        self._eli_login.insert(0, get_setting("elibrary_login"))

        row_pass = ctk.CTkFrame(eli_card, fg_color="transparent")
        row_pass.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(row_pass, text="Пароль", font=font(12),
                     text_color=TEXT_MUTED, width=110, anchor="w").pack(side="left")
        self._eli_pass = styled_entry(row_pass, "пароль", show="•", height=36)
        self._eli_pass.pack(side="left", fill="x", expand=True)
        self._eli_pass.insert(0, get_setting("elibrary_password"))

        self._eli_status = ctk.CTkLabel(eli_card, text="", font=font(11),
                                         text_color=TEXT_GHOST, anchor="w")
        self._eli_status.pack(anchor="w", padx=16, pady=(0, 4))

        primary_btn(eli_card, "Сохранить учётные данные",
                    command=self._save_elibrary_creds, height=36).pack(
                        padx=16, pady=(0, 14), anchor="w")

        return frame

    def _save_elibrary_creds(self):
        login    = self._eli_login.get().strip()
        password = self._eli_pass.get().strip()
        if not login or not password:
            self._eli_status.configure(text="Заполните оба поля", text_color="#cc3333")
            return
        save_setting("elibrary_login",    login)
        save_setting("elibrary_password", password)
        self._eli_status.configure(
            text="Сохранено. Авторизация произойдёт при следующем поиске.",
            text_color=TEXT_GHOST,
        )

    def _build_database(self, parent) -> ctk.CTkFrame:
        frame = scrollable(parent)
        self._section_header(frame, "База данных", "Хранилище и резервные копии")

        card = card_frame(frame)
        card.pack(fill="x", padx=20, pady=(0, 16))

        for label, path, is_dir in [
            ("Файл базы данных",  str(DB_PATH),   False),
            ("Папка данных",      str(DATA_ROOT),  True),
        ]:
            self._path_row(card, label, path, is_dir)

        ctk.CTkFrame(card, height=1, fg_color=BORDER_SOFT,
                     corner_radius=0).pack(fill="x", padx=16, pady=(4, 10))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 14))
        for txt in ["💾  Резервная копия БД", "⬇  Восстановить из копии"]:
            secondary_btn(btn_row, txt, height=36).pack(
                side="left", padx=(0, 8))

        return frame

    def _path_row(self, parent, label: str, path: str, is_dir: bool):
        outer = ctk.CTkFrame(parent, fg_color="transparent")
        outer.pack(fill="x", padx=16, pady=(12, 0))

        ctk.CTkLabel(outer, text=label, font=font(11, "bold"),
                     text_color=TEXT_GHOST, anchor="w").pack(anchor="w", pady=(0, 4))

        bar = ctk.CTkFrame(outer, fg_color=BG, corner_radius=6,
                           border_width=1, border_color=BORDER_SOFT)
        bar.pack(fill="x")
        bar.grid_columnconfigure(0, weight=1)

        entry = ctk.CTkEntry(
            bar, font=font(11, mono=True), text_color=TEXT_MUTED,
            fg_color="transparent", border_width=0, state="normal",
        )
        entry.insert(0, path)
        entry.configure(state="readonly")
        entry.grid(row=0, column=0, sticky="ew", padx=(8, 4), pady=6)

        btns = ctk.CTkFrame(bar, fg_color="transparent")
        btns.grid(row=0, column=1, padx=(0, 6), pady=4)

        ctk.CTkButton(
            btns, text="Копировать", width=84, height=26,
            font=font(11), corner_radius=4,
            fg_color="transparent", hover_color=BG_DEEP,
            text_color=TEXT_MUTED, border_width=1, border_color=BORDER_SOFT,
            command=lambda p=path: self._copy_path(p),
        ).pack(side="left", padx=(0, 4))

        if is_dir:
            ctk.CTkButton(
                btns, text="Открыть", width=70, height=26,
                font=font(11), corner_radius=4,
                fg_color="transparent", hover_color=BG_DEEP,
                text_color=TEXT_MUTED, border_width=1, border_color=BORDER_SOFT,
                command=lambda p=path: self._open_folder(p),
            ).pack(side="left")

    def _copy_path(self, path: str):
        self.clipboard_clear()
        self.clipboard_append(path)

    def _open_folder(self, path: str):
        try:
            os.startfile(path)
        except Exception:
            subprocess.run(["explorer", path], check=False)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _section_header(self, parent, title: str, sub: str):
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(20, 16))
        ctk.CTkLabel(hdr, text=title,
                     font=font(18, "bold"), text_color=TEXT).pack(anchor="w")
        section_label(hdr, sub, pady=(2, 0))

    def _cfg_row(self, parent, label: str, placeholder: str, show: str = ""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkLabel(row, text=label, font=font(12),
                     text_color=TEXT_MUTED, width=140, anchor="w").pack(side="left")
        styled_entry(row, placeholder, show=show, height=36).pack(
            side="left", fill="x", expand=True)

    def _show_section(self, key: str):
        self._section_frames[key].lift()
        for k, btn in self._section_btns.items():
            active = (k == key)
            btn.configure(
                fg_color=PAPER if active else "transparent",
                text_color=TEXT if active else TEXT_MUTED,
                font=font(13, "bold" if active else "normal"),
                border_width=BORDER_W if active else 0,
                border_color=BORDER if active else BG_ALT,
            )

    # ── Users management ───────────────────────────────────────────────────

    def _refresh_users(self):
        for w in self._users_frame.winfo_children():
            w.destroy()

        for idx, u in enumerate(get_all_users(), start=1):
            uname  = u["username"]
            is_adm = bool(u["is_admin"])
            is_self = uname == self.current_user["username"]

            row = ctk.CTkFrame(self._users_frame, fg_color="transparent",
                               corner_radius=3)
            row.pack(fill="x", pady=1)

            # Index
            ctk.CTkLabel(row, text=str(idx), font=font(12, mono=True),
                         text_color=TEXT_GHOST, width=32, anchor="w").pack(
                             side="left", padx=(12, 4), pady=8)

            # Username + (you) badge
            name_row = ctk.CTkFrame(row, fg_color="transparent")
            name_row.pack(side="left", fill="x", expand=True, padx=4, pady=8)
            ctk.CTkLabel(name_row, text=uname,
                         font=font(13, "bold"), text_color=TEXT,
                         anchor="w").pack(side="left")
            if is_self:
                ctk.CTkLabel(name_row, text="  (вы)",
                             font=font(11), text_color=TEXT_GHOST).pack(side="left")

            # Role chip
            role_chip = ctk.CTkFrame(row,
                                     fg_color=ACCENT if is_adm else BG_DEEP,
                                     corner_radius=3, width=80)
            role_chip.pack(side="left", padx=8, pady=10)
            ctk.CTkLabel(role_chip,
                         text="админ" if is_adm else "польз.",
                         font=font(11, "bold"),
                         text_color=PAPER if is_adm else TEXT_MUTED).pack(
                             padx=8, pady=2)

            # Actions
            acts = ctk.CTkFrame(row, fg_color="transparent")
            acts.pack(side="right", padx=8, pady=6)

            ctk.CTkButton(acts, text="🔑", width=34, height=30,
                          fg_color=BG_DEEP, hover_color=BG_ALT,
                          text_color=TEXT_MUTED, corner_radius=3,
                          command=lambda n=uname: ChangePasswordDialog(self, n)
                          ).pack(side="left", padx=(0, 4))

            del_state = "normal" if not is_self else "disabled"
            ctk.CTkButton(acts, text="🗑", width=34, height=30,
                          fg_color=BG_DEEP if is_self else "#fff0f0",
                          hover_color=BG_ALT if is_self else "#ffe0e0",
                          text_color=TEXT_GHOST if is_self else "#cc3333",
                          corner_radius=3,
                          state=del_state,
                          command=lambda n=uname: self._delete_user(n)
                          ).pack(side="left")

            divider(self._users_frame, padx=0, pady=0)

    def _open_add_user(self):
        AddUserDialog(self, on_created=self._refresh_users)

    def _delete_user(self, username: str):
        delete_user(username)
        self._refresh_users()
