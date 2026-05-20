import customtkinter as ctk
from ui.theme import (
    BG_ALT, PAPER, TEXT, TEXT_MUTED, TEXT_GHOST,
    BORDER_SOFT, ACCENT,
    font, section_label, divider, card_frame,
)


class AnalyticsTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._build()

    # ──────────────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Stat cards ────────────────────────────────────────────────────
        stats_row = ctk.CTkFrame(self, fg_color="transparent")
        stats_row.pack(fill="x", padx=16, pady=(16, 12))

        for title, value, hint in [
            ("Статей в базе",   "0", "добавьте первую статью"),
            ("Авторов",         "0", "отслеживается"),
            ("Поисков",         "0", "за всё время"),
            ("Обзоров создано", "0", "через Ollama"),
        ]:
            card = card_frame(stats_row)
            card.pack(side="left", fill="x", expand=True, padx=(0, 8))

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(padx=14, pady=12)

            section_label(inner, title, pady=(0, 2))
            ctk.CTkLabel(inner, text=value,
                         font=font(32, "bold"), text_color=TEXT,
                         anchor="w").pack(fill="x")
            ctk.CTkLabel(inner, text=hint,
                         font=font(11), text_color=ACCENT,
                         anchor="w").pack(fill="x")

        divider(self, padx=16, pady=(0, 12))

        # ── Bottom charts sections ────────────────────────────────────────
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        for title, hint in [
            ("Источники статей",
             "Здесь будет распределение по базам данных"),
            ("Области знаний",
             "Здесь будет распределение по научным дисциплинам"),
        ]:
            card = card_frame(bottom)
            card.pack(side="left", fill="both", expand=True, padx=(0, 8))

            section_label(card, title, padx=16, pady=(16, 8))
            divider(card, padx=16, pady=(0, 0))

            ctk.CTkLabel(card, text=hint,
                         font=font(13), text_color=TEXT_GHOST,
                         justify="center").pack(expand=True, pady=48)
