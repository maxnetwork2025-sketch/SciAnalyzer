import customtkinter as ctk
from core.paths import bundled
from db import reset_password
from ui.theme import (
    BG, BG_ALT, PAPER, TEXT, TEXT_MUTED, TEXT_GHOST,
    BORDER, BORDER_W, BORDER_SOFT, ACCENT, ACCENT_SOFT,
    SUCCESS, DANGER,
    font, styled_entry, card_frame, primary_btn, secondary_btn,
)


class SetPasswordWindow(ctk.CTk):
    """Показывается при первом входе, когда пользователь ещё не задал пароль."""

    def __init__(self, username: str):
        super().__init__()
        self.username = username
        self.password_set = False

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.title("SciAnalyzer — Установка пароля")
        self.resizable(True, True)
        self.configure(fg_color=BG)
        self.iconbitmap(str(bundled("paigeForStatusBar.ico")))

        self._pw_var = ctk.StringVar()
        self._build()
        # trace after _build so self._req_* labels already exist
        self._pw_var.trace_add("write", self._update_requirements)

        self.update_idletasks()
        w, h = 440, 560
        self.minsize(420, 480)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        self.bind("<Return>", lambda _: self._on_save())

    # ──────────────────────────────────────────────────────────────────────────

    def _build(self):
        # Grid layout:
        #   row 0 — flexible top spacer  (weight=1)
        #   row 1 — form content          (weight=0)
        #   row 2 — flexible mid spacer   (weight=1)
        #   row 3 — action buttons        (weight=0, always visible at bottom)
        #
        # Rows 0 & 2 share extra space equally → content centred above buttons.
        # Buttons always rendered last → never hidden when window is small.
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # ── Action buttons (row 3 — pinned to window bottom) ──────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="ew", padx=40, pady=(8, 24))

        secondary_btn(btn_row, "Отмена", command=self.destroy).pack(
            side="left", expand=True, fill="x", padx=(0, 6))
        primary_btn(btn_row, "Готово", command=self._on_save).pack(
            side="left", expand=True, fill="x", padx=(6, 0))

        # ── Form content (row 1 — centred between top and buttons) ────────
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=1, column=0, sticky="ew", padx=40)

        # "ПЕРВЫЙ ВХОД" tag chip
        chip_wrap = ctk.CTkFrame(center, fg_color="transparent")
        chip_wrap.pack()
        chip = ctk.CTkFrame(chip_wrap, fg_color=ACCENT_SOFT, corner_radius=3,
                            border_width=2, border_color=ACCENT)
        chip.pack()
        ctk.CTkLabel(chip, text="ПЕРВЫЙ ВХОД",
                     font=font(10, "bold"), text_color=ACCENT).pack(padx=12, pady=4)

        ctk.CTkLabel(center, text="Задайте пароль",
                     font=font(24, "bold"), text_color=TEXT).pack(pady=(12, 4))
        ctk.CTkLabel(center, text=f"Пользователь: {self.username}",
                     font=font(13), text_color=TEXT_MUTED).pack(pady=(0, 16))

        # ── Form card ─────────────────────────────────────────────────────
        card = card_frame(center)
        card.pack(fill="x")

        ctk.CTkLabel(card, text="НОВЫЙ ПАРОЛЬ",
                     font=font(10, "bold"), text_color=TEXT_GHOST,
                     anchor="w").pack(anchor="w", padx=20, pady=(16, 3))
        self.new_pass = styled_entry(card, placeholder="Минимум 4 символа",
                                     show="•", textvariable=self._pw_var)
        self.new_pass.pack(padx=20, fill="x")

        ctk.CTkLabel(card, text="ПОВТОРИТЕ",
                     font=font(10, "bold"), text_color=TEXT_GHOST,
                     anchor="w").pack(anchor="w", padx=20, pady=(10, 3))
        self.confirm_pass = styled_entry(card, placeholder="Повторите пароль", show="•")
        self.confirm_pass.pack(padx=20, fill="x")

        # ── Requirements indicator ────────────────────────────────────────
        req_card = ctk.CTkFrame(card, fg_color=BG_ALT, corner_radius=3,
                                border_width=1, border_color=BORDER_SOFT)
        req_card.pack(padx=20, pady=(12, 0), fill="x")

        self._req_len = ctk.CTkLabel(
            req_card, text="○  8+ символов",
            font=font(12), text_color=TEXT_GHOST, anchor="w")
        self._req_len.pack(anchor="w", padx=14, pady=(8, 2))

        self._req_digit = ctk.CTkLabel(
            req_card, text="○  цифра",
            font=font(12), text_color=TEXT_GHOST, anchor="w")
        self._req_digit.pack(anchor="w", padx=14, pady=2)

        self._req_special = ctk.CTkLabel(
            req_card, text="○  спецсимвол",
            font=font(12), text_color=TEXT_GHOST, anchor="w")
        self._req_special.pack(anchor="w", padx=14, pady=(2, 8))

        # ── Error label ───────────────────────────────────────────────────
        self.error_label = ctk.CTkLabel(card, text="",
                                         text_color=DANGER, font=font(12))
        self.error_label.pack(pady=(4, 12))

    # ──────────────────────────────────────────────────────────────────────────

    def _update_requirements(self, *_):
        pw = self._pw_var.get()
        has_len     = len(pw) >= 8
        has_digit   = any(c.isdigit() for c in pw)
        has_special = any(not c.isalnum() for c in pw)

        def _apply(label, met: bool, text: str):
            label.configure(
                text=f"{'✓' if met else '○'}  {text}",
                text_color=SUCCESS if met else TEXT_GHOST,
            )

        _apply(self._req_len,     has_len,     "8+ символов")
        _apply(self._req_digit,   has_digit,   "цифра")
        _apply(self._req_special, has_special, "спецсимвол")

    # ──────────────────────────────────────────────────────────────────────────

    def _on_save(self):
        new     = self.new_pass.get()
        confirm = self.confirm_pass.get()

        if not new:
            self.error_label.configure(text="Введите новый пароль")
            return
        if len(new) < 4:
            self.error_label.configure(text="Пароль минимум 4 символа")
            return
        if new != confirm:
            self.error_label.configure(text="Пароли не совпадают")
            self.confirm_pass.delete(0, "end")
            self.confirm_pass.focus()
            return

        reset_password(self.username, new)
        self.password_set = True
        self.destroy()
