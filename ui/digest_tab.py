import customtkinter as ctk
from ui.theme import (
    BG_ALT, PAPER, TEXT, TEXT_MUTED, TEXT_GHOST,
    BORDER_SOFT, ACCENT, ACCENT_HOV,
    font, styled_entry, section_label, divider,
    primary_btn, secondary_btn, option_menu, card_frame, scrollable,
)


class DigestTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._build()

    # ──────────────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Left panel — params ────────────────────────────────────────────
        left = ctk.CTkFrame(self, width=272, corner_radius=0, fg_color=BG_ALT)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        ctk.CTkFrame(self, width=2, corner_radius=0,
                     fg_color=BORDER_SOFT).pack(side="left", fill="y")

        section_label(left, "Параметры обзора", padx=16, pady=(16, 12))

        self._lbl(left, "Тема обзора")
        self.topic_entry = styled_entry(
            left, placeholder="Например: трансформерные архитектуры", height=40)
        self.topic_entry.pack(padx=16, fill="x", pady=(2, 12))

        self._lbl(left, "Количество статей")
        slider_row = ctk.CTkFrame(left, fg_color="transparent")
        slider_row.pack(padx=16, fill="x", pady=(2, 12))
        self.slider = ctk.CTkSlider(
            slider_row, from_=3, to=20, number_of_steps=17,
            button_color=ACCENT, button_hover_color=ACCENT_HOV,
            progress_color=ACCENT,
            command=self._on_slider)
        self.slider.set(10)
        self.slider.pack(side="left", fill="x", expand=True)
        self.slider_lbl = ctk.CTkLabel(
            slider_row, text="10", width=28,
            font=font(12, mono=True), text_color=TEXT_MUTED)
        self.slider_lbl.pack(side="left", padx=(8, 0))

        self._lbl(left, "Формат вывода")
        self.format_menu = option_menu(
            left, ["Тезисы", "Краткий обзор",
                   "Развёрнутый обзор", "Введение к статье"])
        self.format_menu.pack(padx=16, fill="x", pady=(2, 12))

        self._lbl(left, "Язык вывода")
        self.lang_menu = option_menu(left, ["Русский", "English"])
        self.lang_menu.pack(padx=16, fill="x", pady=(2, 16))

        divider(left, padx=16, pady=(0, 14))

        primary_btn(left, "Сгенерировать обзор", height=42).pack(
            padx=16, fill="x")
        secondary_btn(left, "Экспорт", height=36).pack(
            padx=16, fill="x", pady=(8, 0))

        # ── Right panel — output ───────────────────────────────────────────
        right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        # Empty state centred with place
        empty = ctk.CTkFrame(right, fg_color="transparent")
        empty.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(empty, text="Обзор ещё не создан",
                     font=font(18, "bold"), text_color=TEXT).pack(pady=(0, 8))
        ctk.CTkLabel(empty,
                     text="Введите тему и нажмите «Сгенерировать обзор»\n"
                          "Модель Ollama должна быть запущена локально",
                     font=font(13), text_color=TEXT_GHOST,
                     justify="center").pack()

    def _lbl(self, parent, text: str):
        ctk.CTkLabel(parent, text=text, font=font(12),
                     text_color=TEXT_MUTED, anchor="w").pack(anchor="w", padx=16)

    def _on_slider(self, val):
        self.slider_lbl.configure(text=str(int(val)))
