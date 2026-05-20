import os
import re
import tempfile
import threading
import tkinter as tk
import webbrowser
from pathlib import Path

import customtkinter as ctk

from core.api_client import SciAPIClient, Article, SOURCES, SOURCE_LABELS
from core.cyberleninka import CyberLeninkaScraper
from core.sibac import SibacScraper
from core.moluch import MoluchScraper
from core.elibrary import ElibraryScaper
from core.downloader import download_article, pdf_to_txt, save_as_txt
from core.summarizer import Summarizer
from core.translator import Translator
from db import save_downloaded_article, save_search_history, get_search_history
from ui.document_viewer import open_document
from ui.theme import (
    BG, BG_ALT, BG_DEEP, PAPER, TEXT, TEXT_MUTED, TEXT_GHOST,
    BORDER, BORDER_SOFT, ACCENT, ACCENT_SOFT, SUCCESS,
    font, styled_entry, section_label, divider,
    primary_btn, secondary_btn, card_frame, option_menu, scrollable,
)

_SOURCE_COLORS = {
    "arXiv":            ("#fff3ee", ACCENT,     ACCENT),
    "PubMed":           ("#e8f4ec", "#2e7d52",  "#2e7d52"),
    "Semantic Scholar": (BG_DEEP,   TEXT_MUTED, TEXT_MUTED),
    "CyberLeninka":     ("#eef2ff", "#3b5bdb",  "#3b5bdb"),
    "SibAC":            ("#fff8e1", "#b45309",  "#b45309"),
    "МолодойУчёный":   ("#fdf4ff", "#7e22ce",  "#7e22ce"),
    "eLibrary":         ("#eff6ff", "#1d4ed8",  "#1d4ed8"),
}

_MAX_OPTIONS = ["5", "10", "20", "50"]

_SCOUT_SITES = [
    ("cyberleninka.ru", "RU", True),
    ("sibac.info",      "RU", True),
    ("moluch.ru",       "RU", True),
    ("elibrary.ru",     "RU", False),
]

# Минимальная рекомендуемая задержка (сек) для каждого сайта
_SITE_MIN_DELAY = {
    "cyberleninka.ru": 1.0,
    "sibac.info":      2.0,
    "moluch.ru":       2.0,
    "elibrary.ru":     3.0,
}


class SearchTab(ctk.CTkFrame):
    def __init__(self, parent, current_user: dict):
        super().__init__(parent, fg_color="transparent")
        self._current_user      = current_user
        self._client            = SciAPIClient()
        self._cy_scraper        = CyberLeninkaScraper()
        self._sibac_scraper     = SibacScraper()
        self._moluch_scraper    = MoluchScraper()
        self._elibrary_scraper  = ElibraryScaper()
        self._translator        = Translator()
        self._summarizer        = Summarizer()
        # catalog state
        self._mode              = "topic"
        self._mode_btns:        dict = {}
        self._source_vars:      dict[str, ctk.BooleanVar] = {}
        self._auto_translate_var = ctk.BooleanVar(value=True)
        self._searching         = False
        self._last_query        = ""
        self._hist_top          = None   # Toplevel dropdown для Картотеки
        # scout state
        self._scout_mode        = "topic"
        self._scout_mode_btns:  dict = {}
        self._scout_searching   = False
        self._scout_last_query  = ""
        self._scout_hist_top    = None   # Toplevel dropdown для Разведки
        # sub-tab state
        self._sub_btns:         dict = {}
        self._sub_frames:       dict = {}
        self._build()
        # Bind once after layout is complete
        self.after(100, self._bind_global_click)

    # ──────────────────────────────────────────────────────────────────────────
    #  Top-level layout
    # ──────────────────────────────────────────────────────────────────────────

    def _build(self):
        self._build_subtab_bar()

        content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        content.pack(fill="both", expand=True)
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        catalog_frame = ctk.CTkFrame(content, fg_color="transparent", corner_radius=0)
        catalog_frame.grid(row=0, column=0, sticky="nsew")
        self._sub_frames["catalog"] = catalog_frame
        self._build_catalog(catalog_frame)

        scout_frame = ctk.CTkFrame(content, fg_color="transparent", corner_radius=0)
        scout_frame.grid(row=0, column=0, sticky="nsew")
        self._sub_frames["scout"] = scout_frame
        self._build_scout(scout_frame)

        self._switch_sub("catalog")

    # ──────────────────────────────────────────────────────────────────────────
    #  Sub-tab bar
    # ──────────────────────────────────────────────────────────────────────────

    def _build_subtab_bar(self):
        bar = ctk.CTkFrame(self, height=58, corner_radius=0, fg_color=BG_ALT)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        ctk.CTkFrame(self, height=1, corner_radius=0,
                     fg_color=BORDER_SOFT).pack(fill="x")

        _TABS = [
            ("catalog", "📚", "Картотека", "через API"),
            ("scout",   "🛰",  "Разведка",  "через скрапер"),
        ]

        tabs_row = ctk.CTkFrame(bar, fg_color="transparent")
        tabs_row.pack(side="left", fill="y", padx=8)

        for key, icon, label, sub in _TABS:
            tab = ctk.CTkFrame(tabs_row, fg_color="transparent",
                               corner_radius=4, cursor="hand2")
            tab.pack(side="left", fill="y", padx=(0, 2), pady=6)

            # Icon square 22×22
            icon_sq = ctk.CTkFrame(tab, width=22, height=22,
                                   corner_radius=3, fg_color=BG_DEEP,
                                   border_width=1, border_color=BORDER_SOFT)
            icon_sq.pack(side="left", padx=(10, 0), pady=8)
            icon_sq.pack_propagate(False)
            icon_lbl = ctk.CTkLabel(icon_sq, text=icon, font=font(11),
                                    text_color=TEXT_MUTED)
            icon_lbl.pack(expand=True)

            # Text block: name + subtitle
            text_block = ctk.CTkFrame(tab, fg_color="transparent")
            text_block.pack(side="left", padx=8, pady=4)
            name_lbl = ctk.CTkLabel(text_block, text=label,
                                    font=font(13, "bold"), text_color=TEXT_MUTED,
                                    anchor="w")
            name_lbl.pack(anchor="w")
            sub_lbl = ctk.CTkLabel(text_block, text=sub,
                                   font=font(10), text_color=TEXT_GHOST,
                                   anchor="w")
            sub_lbl.pack(anchor="w")

            # Right padding
            ctk.CTkFrame(tab, width=10, fg_color="transparent").pack(side="left")

            # Bind clicks to every element so the whole tab is clickable
            for w in [tab, icon_sq, icon_lbl, text_block, name_lbl, sub_lbl]:
                w.bind("<Button-1>", lambda e, k=key: self._switch_sub(k))

            self._sub_btns[key] = {
                "tab": tab, "icon_sq": icon_sq,
                "icon_lbl": icon_lbl, "name_lbl": name_lbl,
            }

    def _switch_sub(self, key: str):
        self._sub_frames[key].tkraise()
        for k, w in self._sub_btns.items():
            active = (k == key)
            w["tab"].configure(fg_color=PAPER if active else "transparent")
            w["icon_sq"].configure(
                fg_color=ACCENT if active else BG_DEEP,
                border_color=ACCENT if active else BORDER_SOFT,
            )
            w["icon_lbl"].configure(text_color=PAPER if active else TEXT_MUTED)
            w["name_lbl"].configure(
                text_color=TEXT if active else TEXT_MUTED,
                font=font(13, "bold"),
            )

    # ──────────────────────────────────────────────────────────────────────────
    #  Catalog sub-tab (API search — содержимое прежней вкладки «Поиск»)
    # ──────────────────────────────────────────────────────────────────────────

    def _build_catalog(self, parent):
        # ── Left panel — filters ──────────────────────────────────────────
        left = ctk.CTkFrame(parent, width=260, corner_radius=0, fg_color=BG_ALT)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        ctk.CTkFrame(parent, width=2, corner_radius=0,
                     fg_color=BORDER_SOFT).pack(side="left", fill="y")

        section_label(left, "Источники", padx=16, pady=(16, 10))

        for src in SOURCES:
            var = ctk.BooleanVar(value=(src != "semantic_scholar"))
            self._source_vars[src] = var
            ctk.CTkCheckBox(
                left,
                text=SOURCE_LABELS[src],
                variable=var,
                font=font(13),
                text_color=TEXT_MUTED,
                fg_color=ACCENT,
                hover_color=ACCENT_SOFT,
                border_color=BORDER,
                border_width=2,
                checkmark_color=PAPER,
                corner_radius=2,
            ).pack(anchor="w", padx=16, pady=3)

        divider(left, padx=16, pady=(14, 12))
        section_label(left, "Результатов на источник", padx=16, pady=(0, 6))

        self._max_menu = option_menu(left, _MAX_OPTIONS)
        self._max_menu.set("10")
        self._max_menu.pack(padx=16, fill="x", pady=(0, 16))

        divider(left, padx=16, pady=(0, 12))
        ctk.CTkCheckBox(
            left,
            text="Авто-перевод запроса",
            variable=self._auto_translate_var,
            font=font(13),
            text_color=TEXT_MUTED,
            fg_color=ACCENT,
            hover_color=ACCENT_SOFT,
            border_color=BORDER,
            border_width=2,
            checkmark_color=PAPER,
            corner_radius=2,
        ).pack(anchor="w", padx=16, pady=(0, 4))
        ctk.CTkLabel(left,
                     text="Искать на рус. и англ.",
                     font=font(11), text_color=TEXT_GHOST).pack(
                         anchor="w", padx=32, pady=(0, 8))

        ctk.CTkFrame(left, fg_color="transparent").pack(expand=True, fill="both")
        secondary_btn(left, "Сбросить фильтры",
                      command=self._reset_filters,
                      height=36).pack(padx=16, fill="x", pady=12)

        # ── Right panel ───────────────────────────────────────────────────
        right = ctk.CTkFrame(parent, corner_radius=0, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        section_label(right, "Картотека · по API источников",
                      padx=24, pady=(20, 4))
        ctk.CTkLabel(right, text="Что ищем сегодня?",
                     font=font(22, "bold"), text_color=TEXT).pack(
                         anchor="w", padx=24, pady=(0, 12))

        mode_row = ctk.CTkFrame(right, fg_color="transparent")
        mode_row.pack(fill="x", padx=24, pady=(0, 10))
        for key, label in [("topic", "По теме"), ("author", "По автору")]:
            btn = ctk.CTkButton(
                mode_row,
                text=label,
                font=font(12),
                height=30,
                corner_radius=999,
                border_width=2,
                command=lambda k=key: self._set_mode(k),
            )
            btn.pack(side="left", padx=(0, 6))
            self._mode_btns[key] = btn

        search_row = ctk.CTkFrame(right, fg_color="transparent")
        search_row.pack(fill="x", padx=24, pady=(0, 14))
        self.search_entry = styled_entry(
            search_row,
            placeholder="Название, ключевые слова или автор...",
            height=44)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.search_entry.bind("<Return>",   lambda _: self._start_search())
        self.search_entry.bind("<FocusIn>",  lambda _: self._show_history())
        self.search_entry.bind("<Button-1>", lambda _: self._show_history())
        self.search_entry.bind("<FocusOut>", lambda _: self.after(200, self._hide_history))

        self._search_btn = primary_btn(search_row, "Искать",
                                       command=self._start_search, height=44)
        self._search_btn.pack(side="left")
        self._set_mode("topic")

        self._translated_row = ctk.CTkFrame(right, fg_color="transparent")
        self._translated_lbl = ctk.CTkLabel(
            self._translated_row, text="",
            font=font(11), text_color=ACCENT, anchor="w")
        self._translated_lbl.pack(side="left", padx=24)

        divider(right, padx=24, pady=(0, 0))

        self._results_scroll = scrollable(right)
        self._results_scroll.pack(fill="both", expand=True, padx=16, pady=8)

        self._show_idle()

    # ──────────────────────────────────────────────────────────────────────────
    #  Scout sub-tab (scraper — visual-only, backend not connected)
    # ──────────────────────────────────────────────────────────────────────────

    def _build_scout(self, parent):
        # ── Left panel — scraper settings (300px) ─────────────────────────
        left = ctk.CTkFrame(parent, width=300, corner_radius=0, fg_color=BG_ALT)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        ctk.CTkFrame(parent, width=2, corner_radius=0,
                     fg_color=BORDER_SOFT).pack(side="left", fill="y")

        sl = scrollable(left)
        sl.pack(fill="both", expand=True)

        # Целевые сайты
        section_label(sl, "Целевые сайты", padx=16, pady=(16, 8))

        self._scout_site_vars: dict[str, ctk.BooleanVar] = {}
        for url, tag, enabled in _SCOUT_SITES:
            var = ctk.BooleanVar(value=enabled)
            self._scout_site_vars[url] = var

            site_card = ctk.CTkFrame(
                sl,
                fg_color=PAPER if enabled else BG_DEEP,
                corner_radius=3,
                border_width=1,
                border_color=BORDER_SOFT,
            )
            site_card.pack(fill="x", padx=12, pady=2)

            row = ctk.CTkFrame(site_card, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=5)

            ctk.CTkCheckBox(
                row, text="", variable=var, width=20,
                fg_color=ACCENT, hover_color=ACCENT_SOFT,
                border_color=BORDER, border_width=2,
                checkmark_color=PAPER, corner_radius=2,
            ).pack(side="left")

            ctk.CTkLabel(
                row, text=url, font=font(11, mono=True),
                text_color=TEXT if enabled else TEXT_GHOST,
                anchor="w",
            ).pack(side="left", padx=(6, 4), fill="x", expand=True)

            tag_f = ctk.CTkFrame(row, fg_color=ACCENT_SOFT, corner_radius=3)
            tag_f.pack(side="right")
            ctk.CTkLabel(tag_f, text=tag, font=font(9, "bold"),
                         text_color=ACCENT).pack(padx=5, pady=1)


        divider(sl, padx=12, pady=(14, 10))

        # Глубина обхода
        section_label(sl, "Количество статей", padx=16, pady=(0, 8))

        self._scout_depth_var = tk.IntVar(value=3)
        for val, lbl in [(1,  "10 статей"),
                          (3,  "30 статей  (по умолч.)"),
                          (10, "100 статей")]:
            ctk.CTkRadioButton(
                sl,
                text=lbl,
                variable=self._scout_depth_var,
                value=val,
                font=font(12),
                text_color=TEXT_MUTED,
                fg_color=ACCENT,
                hover_color=ACCENT_SOFT,
                border_color=BORDER,
            ).pack(anchor="w", padx=16, pady=2)

        divider(sl, padx=12, pady=(12, 10))

        # Задержка
        section_label(sl, "Задержка между запросами", padx=16, pady=(0, 8))

        delay_row = ctk.CTkFrame(sl, fg_color="transparent")
        delay_row.pack(fill="x", padx=16, pady=(0, 4))

        self._scout_delay_entry = styled_entry(delay_row, "", height=34, width=70)
        self._scout_delay_entry.insert(0, "2")
        self._scout_delay_entry.pack(side="left")
        self._scout_delay_lbl = ctk.CTkLabel(
            delay_row, text="",
            font=font(11), text_color=TEXT_GHOST,
        )
        self._scout_delay_lbl.pack(side="left", padx=(8, 0))

        # Обновляем подсказку при вводе и при изменении выбранных сайтов
        self._scout_delay_entry.bind("<KeyRelease>",
                                     lambda _: self._update_delay_hint())
        for var in self._scout_site_vars.values():
            var.trace_add("write", lambda *_: self._update_delay_hint())

        self._update_delay_hint()  # начальный рендер

        # ── Right panel ───────────────────────────────────────────────────
        right = ctk.CTkFrame(parent, corner_radius=0, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        # Fixed top controls (header, chips, search bar — don't scroll)
        top_bar = ctk.CTkFrame(right, fg_color="transparent")
        top_bar.pack(fill="x")

        # Header + status indicator
        hdr = ctk.CTkFrame(top_bar, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 0))

        hdr_left = ctk.CTkFrame(hdr, fg_color="transparent")
        hdr_left.pack(side="left", fill="y")
        section_label(hdr_left, "Разведка · через скрапер", pady=(0, 4))
        ctk.CTkLabel(hdr_left, text="Куда отправимся?",
                     font=font(22, "bold"), text_color=TEXT).pack(anchor="w")

        # status_f = ctk.CTkFrame(hdr, fg_color=BG_ALT, corner_radius=4,
        #                         border_width=1, border_color=BORDER_SOFT)
        # status_f.pack(side="right", pady=12)
        # srow = ctk.CTkFrame(status_f, fg_color="transparent")
        # srow.pack(padx=10, pady=6)
        # ctk.CTkFrame(srow, width=8, height=8,
        #              corner_radius=4, fg_color="#4a8c6a").pack(side="left", padx=(0, 6))
        # ctk.CTkLabel(srow, text="скрапер готов · 2 сайта",
        #              font=font(11), text_color=TEXT_MUTED).pack(side="left")

        # Mode chips
        mrow = ctk.CTkFrame(top_bar, fg_color="transparent")
        mrow.pack(fill="x", padx=24, pady=(14, 10))
        for k, lbl in [("topic", "По теме"), ("author", "По автору")]:
            btn = ctk.CTkButton(
                mrow, text=lbl, font=font(12), height=30,
                corner_radius=999, border_width=2,
                command=lambda kk=k: self._set_scout_mode(kk),
            )
            btn.pack(side="left", padx=(0, 6))
            self._scout_mode_btns[k] = btn
        self._set_scout_mode("topic")

        # Search bar
        sbar = ctk.CTkFrame(top_bar, fg_color="transparent")
        sbar.pack(fill="x", padx=24, pady=(0, 4))
        self._scout_entry = styled_entry(
            sbar,
            placeholder="🛰  напр. графовые нейронные сети в фармакологии",
            height=50,
        )
        self._scout_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._scout_entry.bind("<Return>",   lambda _: self._scout_start_search())
        self._scout_entry.bind("<FocusIn>",  lambda _: self._scout_show_history())
        self._scout_entry.bind("<Button-1>", lambda _: self._scout_show_history())
        self._scout_entry.bind("<FocusOut>", lambda _: self.after(200, self._scout_hide_history))
        self._scout_search_btn = primary_btn(
            sbar, "Запустить разведку",
            command=self._scout_start_search,
            height=50,
        )
        self._scout_search_btn.pack(side="left")

        # Estimate line
        depth_val = 3
        ctk.CTkLabel(
            top_bar,
            text=f"Будет обойдено ~ {depth_val} страницы  ·  ожидаемое время ~ 30 сек",
            font=font(11), text_color=TEXT_GHOST, anchor="w",
        ).pack(fill="x", padx=24, pady=(0, 4))


        divider(right, padx=24, pady=(0, 0))

        # Scrollable results area
        self._scout_results_scroll = scrollable(right)
        self._scout_results_scroll.pack(fill="both", expand=True, padx=16, pady=8)

        self._scout_show_idle()

    # ──────────────────────────────────────────────────────────────────────────
    #  Mode & filters (catalog)
    # ──────────────────────────────────────────────────────────────────────────

    def _set_mode(self, key: str):
        self._mode = key
        for k, btn in self._mode_btns.items():
            active = (k == key)
            btn.configure(
                fg_color=ACCENT     if active else "transparent",
                text_color=PAPER    if active else TEXT_MUTED,
                border_color=ACCENT if active else BORDER_SOFT,
            )
        hint = ("Название, ключевые слова или автор..."
                if key == "topic"
                else "Фамилия автора, например: Vaswani или Иванов А.П.")
        self.search_entry.configure(placeholder_text=hint)

    def _reset_filters(self):
        for src, var in self._source_vars.items():
            var.set(src != "semantic_scholar")
        self._max_menu.set("10")
        self._auto_translate_var.set(True)

    # ──────────────────────────────────────────────────────────────────────────
    #  Mode (scout)
    # ──────────────────────────────────────────────────────────────────────────

    def _update_delay_hint(self):
        mins = [
            _SITE_MIN_DELAY.get(url, 1.0)
            for url, var in self._scout_site_vars.items()
            if var.get()
        ]
        rec = max(mins) if mins else 1.0

        try:
            current = float(self._scout_delay_entry.get().strip() or "0")
        except ValueError:
            current = 0.0

        if current < rec:
            color = ACCENT   # оранжевый — ниже рекомендуемого
            icon  = "⚠"
        else:
            color = SUCCESS   # зелёный — OK
            icon  = "✓"

        self._scout_delay_lbl.configure(
            text=f"сек  ·  {icon} рекомендуется ≥{rec:.0f} сек",
            text_color=color,
        )

    def _set_scout_mode(self, key: str):
        self._scout_mode = key
        for k, btn in self._scout_mode_btns.items():
            active = (k == key)
            btn.configure(
                fg_color=ACCENT     if active else "transparent",
                text_color=PAPER    if active else TEXT_MUTED,
                border_color=ACCENT if active else BORDER_SOFT,
            )

        hints = {
            "topic":  "🛰  напр. графовые нейронные сети в фармакологии",
            "author": "Фамилия автора, например: Иванов или Smith J",
        }
        if hasattr(self, "_scout_entry"):
            self._scout_entry.configure(placeholder_text=hints.get(key, ""))

    # ──────────────────────────────────────────────────────────────────────────
    #  Search (scout)
    # ──────────────────────────────────────────────────────────────────────────

    def _scout_start_search(self):
        if self._scout_searching:
            return
        query = self._scout_entry.get().strip()
        if not query:
            return

        enabled_sites = [url for url, var in self._scout_site_vars.items() if var.get()]
        if not enabled_sites:
            self._scout_show_message("Выберите хотя бы один сайт в левой панели")
            return

        depth = self._scout_depth_var.get()
        try:
            delay = float(self._scout_delay_entry.get().strip() or "2")
        except ValueError:
            delay = 2.0

        self._scout_searching = True
        self._scout_last_query = query
        self._scout_search_btn.configure(state="disabled", text="Разведка...")
        self._scout_hide_history()
        self._scout_show_loading()
        mode = self._scout_mode

        def worker():
            results: list = []
            errors:  list = []
            seen:    set  = set()

            def add(arts):
                for a in arts:
                    key = a.url or (a.title + a.source)
                    if key not in seen:
                        seen.add(key)
                        results.append(a)

            if "cyberleninka.ru" in enabled_sites:
                try:
                    add(self._cy_scraper.search(
                        query=query, max_results=50,
                        depth=depth, delay=delay, mode=mode,
                    ))
                except Exception as e:
                    errors.append(f"CyberLeninka: {e}")

            if "sibac.info" in enabled_sites:
                try:
                    add(self._sibac_scraper.search(
                        query=query, max_results=50,
                        depth=depth, delay=delay, mode=mode,
                    ))
                except Exception as e:
                    errors.append(f"SibAC: {e}")

            if "moluch.ru" in enabled_sites:
                try:
                    add(self._moluch_scraper.search(
                        query=query, max_results=50,
                        depth=depth, delay=delay, mode=mode,
                    ))
                except Exception as e:
                    errors.append(f"МолодойУчёный: {e}")

            if "elibrary.ru" in enabled_sites:
                try:
                    add(self._elibrary_scraper.search(
                        query=query, max_results=50,
                        depth=depth, delay=delay, mode=mode,
                    ))
                except Exception as e:
                    errors.append(f"eLibrary: {e}")

            self.after(0, lambda r=results, e=errors: self._scout_on_results(r, e))

        threading.Thread(target=worker, daemon=True).start()

    def _scout_on_results(self, results: list, errors: list):
        self._scout_searching = False
        self._scout_search_btn.configure(state="normal", text="Запустить разведку")
        if self._scout_last_query:
            try:
                save_search_history(self._scout_last_query, len(results),
                                    self._current_user["id"])
            except Exception:
                pass
        if results:
            self._scout_show_results(results, errors)
        elif errors:
            self._scout_show_message("Ошибка разведки:\n" + "\n".join(errors[:3]))
        else:
            self._scout_show_message("Ничего не найдено.\nПопробуйте другой запрос.")

    def _scout_clear_results(self):
        for w in self._scout_results_scroll.winfo_children():
            w.destroy()

    def _scout_show_idle(self):
        self._scout_clear_results()
        wrap = ctk.CTkFrame(self._scout_results_scroll, fg_color="transparent")
        wrap.pack(expand=True, pady=64)
        ctk.CTkLabel(wrap, text="Введите запрос и нажмите «Запустить разведку»",
                     font=font(16, "bold"), text_color=TEXT).pack(pady=(0, 8))
        ctk.CTkLabel(wrap,
                     text="Поиск по CyberLeninka, SibAC, МолодойУчёный и eLibrary",
                     font=font(13), text_color=TEXT_GHOST).pack()

    def _scout_show_loading(self):
        self._scout_clear_results()
        wrap = ctk.CTkFrame(self._scout_results_scroll, fg_color="transparent")
        wrap.pack(expand=True, pady=64)
        ctk.CTkLabel(wrap, text="Разведка...",
                     font=font(16, "bold"), text_color=TEXT_MUTED).pack(pady=(0, 6))
        ctk.CTkLabel(wrap, text="Обходим сайты, подождите",
                     font=font(13), text_color=TEXT_GHOST).pack()

    def _scout_show_message(self, text: str):
        self._scout_clear_results()
        wrap = ctk.CTkFrame(self._scout_results_scroll, fg_color="transparent")
        wrap.pack(expand=True, pady=64)
        ctk.CTkLabel(wrap, text=text, font=font(14), text_color=TEXT_MUTED,
                     justify="center").pack()

    def _scout_show_results(self, articles: list, errors: list):
        self._scout_clear_results()
        hdr = ctk.CTkFrame(self._scout_results_scroll, fg_color="transparent")
        hdr.pack(fill="x", padx=4, pady=(4, 6))
        ctk.CTkLabel(hdr, text=f"Найдено: {len(articles)} статей",
                     font=font(13, "bold"), text_color=TEXT).pack(side="left")
        if errors:
            ctk.CTkLabel(hdr,
                         text=f"  ({len(errors)} источника с ошибками)",
                         font=font(11), text_color=TEXT_GHOST).pack(side="left")

        for article in articles:
            try:
                self._article_card(self._scout_results_scroll, article)
            except Exception:
                pass

        secondary_btn(
            self._scout_results_scroll, "← Вернуться к началу",
            command=self._scout_show_idle,
            height=32,
        ).pack(padx=4, pady=(8, 4))

    # ──────────────────────────────────────────────────────────────────────────
    #  Search (catalog)
    # ──────────────────────────────────────────────────────────────────────────

    def _start_search(self):
        if self._searching:
            return
        query = self.search_entry.get().strip()
        if not query:
            return

        self._hide_history()
        sources = [s for s, v in self._source_vars.items() if v.get()]
        if not sources:
            self._show_message("Выберите хотя бы один источник")
            return

        max_n = int(self._max_menu.get())
        self._searching = True
        self._last_query = query
        self._search_btn.configure(state="disabled", text="Поиск...")
        self._translated_row.pack_forget()
        self._show_loading()
        self.update_idletasks()
        do_translate = self._auto_translate_var.get() and self._mode != "author"

        def worker():
            translated = None
            query_en   = None

            if do_translate and self._translator.is_available():
                eng = self._translator.translate_to_english(query)
                if eng and eng != query:
                    query_en  = eng
                    translated = eng

            results: list = []
            errors:  list = []
            seen:    set  = set()

            def add(articles):
                for a in articles:
                    key = a.url or (a.title + a.source)
                    if key not in seen:
                        seen.add(key)
                        results.append(a)

            for src in sources:
                try:
                    add(self._client.search_source(src, query, self._mode, max_n))
                    if query_en:
                        add(self._client.search_source(src, query_en, self._mode, max_n))
                except Exception as e:
                    errors.append(f"{src}: {e}")

            self.after(0, lambda r=results, e=errors, t=translated:
                       self._on_results(r, e, t))

        threading.Thread(target=worker, daemon=True).start()

    def _on_results(self, results: list, errors: list,
                    translated: str | None = None):
        self._searching = False
        self._search_btn.configure(state="normal", text="Искать")
        if self._last_query:
            try:
                save_search_history(self._last_query, len(results),
                                    self._current_user["id"])
            except Exception:
                pass
        if translated:
            self._translated_lbl.configure(text=f"Переведено: «{translated}»")
            self._translated_row.pack(fill="x", pady=(0, 4))
        else:
            self._translated_row.pack_forget()
        try:
            if results:
                self._show_results(results, errors)
            elif errors:
                self._show_message(
                    "Ошибка при получении данных:\n" + "\n".join(errors[:3])
                )
            else:
                self._show_message(
                    "Ничего не найдено.\nПопробуйте другой запрос или источник."
                )
        except Exception as e:
            import traceback, sys
            traceback.print_exc(file=sys.stderr)
            self._show_message(f"Ошибка отображения:\n{e}")

    # ──────────────────────────────────────────────────────────────────────────
    #  History dropdown (catalog)
    # ──────────────────────────────────────────────────────────────────────────

    def _show_history(self):
        rows = get_search_history(self._current_user["id"], limit=5)
        if not rows:
            return

        if self._hist_top is None:
            top = tk.Toplevel(self.winfo_toplevel())
            top.withdraw()
            top.overrideredirect(True)
            top.attributes("-topmost", True)
            self._hist_inner = ctk.CTkFrame(
                top, fg_color=BG_ALT, corner_radius=6,
                border_width=1, border_color=BORDER_SOFT)
            self._hist_inner.pack(fill="both", expand=True)
            self._hist_top = top

        for w in self._hist_inner.winfo_children():
            w.destroy()

        for row in rows:
            q = row["query"]
            ctk.CTkButton(
                self._hist_inner,
                text=q,
                font=font(12),
                fg_color="transparent",
                text_color=TEXT_MUTED,
                hover_color=BG_DEEP,
                anchor="w",
                height=32,
                corner_radius=4,
                command=lambda q=q: self._select_history(q),
            ).pack(fill="x", padx=4, pady=1)

        self.update_idletasks()
        x = self.search_entry.winfo_rootx()
        y = self.search_entry.winfo_rooty() + self.search_entry.winfo_height() + 2
        w = self.search_entry.winfo_width()
        h = len(rows) * 36 + 8
        self._hist_top.geometry(f"{w}x{h}+{x}+{y}")
        self._hist_top.deiconify()
        self._hist_top.lift()

    def _hide_history(self):
        if self._hist_top is not None:
            self._hist_top.withdraw()

    def _select_history(self, query: str):
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, query)
        self._hide_history()

    # ──────────────────────────────────────────────────────────────────────────
    #  History dropdown (scout) — общая история с Картотекой
    # ──────────────────────────────────────────────────────────────────────────

    def _scout_show_history(self):
        rows = get_search_history(self._current_user["id"], limit=5)
        if not rows:
            return

        if self._scout_hist_top is None:
            top = tk.Toplevel(self.winfo_toplevel())
            top.withdraw()
            top.overrideredirect(True)
            top.attributes("-topmost", True)
            self._scout_hist_inner = ctk.CTkFrame(
                top, fg_color=BG_ALT, corner_radius=6,
                border_width=1, border_color=BORDER_SOFT)
            self._scout_hist_inner.pack(fill="both", expand=True)
            self._scout_hist_top = top

        for w in self._scout_hist_inner.winfo_children():
            w.destroy()

        for row in rows:
            q = row["query"]
            ctk.CTkButton(
                self._scout_hist_inner,
                text=q,
                font=font(12),
                fg_color="transparent",
                text_color=TEXT_MUTED,
                hover_color=BG_DEEP,
                anchor="w",
                height=32,
                corner_radius=4,
                command=lambda q=q: self._scout_select_history(q),
            ).pack(fill="x", padx=4, pady=1)

        self.update_idletasks()
        x = self._scout_entry.winfo_rootx()
        y = self._scout_entry.winfo_rooty() + self._scout_entry.winfo_height() + 2
        w = self._scout_entry.winfo_width()
        h = len(rows) * 36 + 8
        self._scout_hist_top.geometry(f"{w}x{h}+{x}+{y}")
        self._scout_hist_top.deiconify()
        self._scout_hist_top.lift()

    def _scout_hide_history(self):
        if self._scout_hist_top is not None:
            self._scout_hist_top.withdraw()

    def _scout_select_history(self, query: str):
        self._scout_entry.delete(0, "end")
        self._scout_entry.insert(0, query)
        self._scout_hide_history()

    # ── Global click-outside handler ──────────────────────────────────────────

    def _bind_global_click(self):
        root = self.winfo_toplevel()
        root.bind("<Button-1>", self._on_global_click, add="+")

    def _on_global_click(self, event):
        w = event.widget
        # Allow clicks on either search entry (inner tk.Entry widget)
        try:
            if w is self.search_entry._entry:
                return
        except Exception:
            pass
        try:
            if w is self._scout_entry._entry:
                return
        except Exception:
            pass
        # Allow clicks inside the dropdown Toplevels themselves
        for top in (self._hist_top, self._scout_hist_top):
            if top is None:
                continue
            try:
                if not top.winfo_ismapped():
                    continue
                tx, ty = top.winfo_rootx(), top.winfo_rooty()
                tw, th = top.winfo_width(), top.winfo_height()
                if tx <= event.x_root <= tx + tw and ty <= event.y_root <= ty + th:
                    return
            except Exception:
                pass
        self._hide_history()
        self._scout_hide_history()

    # ──────────────────────────────────────────────────────────────────────────
    #  Results rendering (catalog)
    # ──────────────────────────────────────────────────────────────────────────

    def _clear_results(self):
        for w in self._results_scroll.winfo_children():
            w.destroy()

    def _show_idle(self):
        self._clear_results()
        wrap = ctk.CTkFrame(self._results_scroll, fg_color="transparent")
        wrap.pack(expand=True, pady=64)
        ctk.CTkLabel(wrap, text="Введите запрос и нажмите «Искать»",
                     font=font(16, "bold"), text_color=TEXT).pack(pady=(0, 8))
        ctk.CTkLabel(wrap,
                     text="Поиск одновременно по arXiv, PubMed и Semantic Scholar",
                     font=font(13), text_color=TEXT_GHOST).pack()

    def _show_loading(self):
        self._clear_results()
        wrap = ctk.CTkFrame(self._results_scroll, fg_color="transparent")
        wrap.pack(expand=True, pady=64)
        self._loading_label = ctk.CTkLabel(
            wrap, text="Поиск...",
            font=font(16, "bold"), text_color=TEXT_MUTED)
        self._loading_label.pack(pady=(0, 6))
        ctk.CTkLabel(wrap,
                     text="Запрашиваем базы данных, подождите",
                     font=font(13), text_color=TEXT_GHOST).pack()

    def _show_message(self, text: str):
        self._clear_results()
        wrap = ctk.CTkFrame(self._results_scroll, fg_color="transparent")
        wrap.pack(expand=True, pady=64)
        ctk.CTkLabel(wrap, text=text,
                     font=font(14), text_color=TEXT_MUTED,
                     justify="center").pack()

    def _show_results(self, articles: list, errors: list):
        self._clear_results()

        hdr = ctk.CTkFrame(self._results_scroll, fg_color="transparent")
        hdr.pack(fill="x", padx=4, pady=(4, 6))
        ctk.CTkLabel(hdr,
                     text=f"Найдено: {len(articles)} статей",
                     font=font(13, "bold"), text_color=TEXT).pack(side="left")
        if errors:
            ctk.CTkLabel(hdr,
                         text=f"  ({len(errors)} источника недоступны)",
                         font=font(11), text_color=TEXT_GHOST).pack(side="left")

        for article in articles:
            try:
                self._article_card(self._results_scroll, article)
            except Exception:
                pass

    def _article_card(self, parent, article: Article):
        card = card_frame(parent)
        card.pack(fill="x", padx=4, pady=4)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x", pady=(0, 6))

        bg, fg, _ = _SOURCE_COLORS.get(article.source, (BG_DEEP, TEXT_MUTED, TEXT_MUTED))
        badge = ctk.CTkFrame(top, fg_color=bg, corner_radius=3)
        badge.pack(side="left")
        ctk.CTkLabel(badge, text=article.source,
                     font=font(10, "bold"), text_color=fg).pack(padx=8, pady=2)

        if article.year:
            ctk.CTkLabel(top, text=article.year,
                         font=font(11, mono=True),
                         text_color=TEXT_GHOST).pack(side="left", padx=(8, 0))

        title_lbl = ctk.CTkLabel(inner, text=article.title,
                                  font=font(14, "bold"), text_color=TEXT,
                                  anchor="w", wraplength=640, justify="left")
        title_lbl.pack(fill="x", pady=(0, 4))

        if article.source == "PubMed":
            ctk.CTkLabel(inner,
                         text="Только аннотация — PubMed не предоставляет полный текст статьи",
                         font=font(11), text_color=TEXT_GHOST,
                         anchor="w").pack(fill="x", pady=(0, 4))

        if article.source == "SibAC":
            ctk.CTkLabel(inner,
                         text="Краткая научная статья из сборника · при скачивании загружается весь выпуск журнала",
                         font=font(11), text_color=TEXT_GHOST,
                         anchor="w").pack(fill="x", pady=(0, 4))

        if article.source == "МолодойУчёный":
            ctk.CTkLabel(inner,
                         text="Статья журнала «Молодой учёный» · индексируется в РИНЦ",
                         font=font(11), text_color=TEXT_GHOST,
                         anchor="w").pack(fill="x", pady=(0, 4))

        if article.source == "eLibrary":
            ctk.CTkLabel(inner,
                         text="Источник: Научная электронная библиотека eLibrary.ru · индексируется в РИНЦ",
                         font=font(11), text_color=TEXT_GHOST,
                         anchor="w").pack(fill="x", pady=(0, 4))

        if article.authors:
            ctk.CTkLabel(inner, text=self._format_authors(article.authors),
                         font=font(12), text_color=TEXT_MUTED,
                         anchor="w").pack(fill="x", pady=(0, 6))

        if article.url:
            bot = ctk.CTkFrame(inner, fg_color="transparent")
            bot.pack(fill="x")

            ctk.CTkLabel(bot, text=article.url,
                         font=font(11, mono=True), text_color=TEXT_GHOST,
                         anchor="w").pack(side="left", fill="x", expand=True,
                                          padx=(0, 8))

            btn_col = ctk.CTkFrame(bot, fg_color="transparent")
            btn_col.pack(side="right")

            tr_btn = secondary_btn(btn_col, "Перевести название",
                                   command=None, height=28)
            tr_btn.configure(
                command=lambda a=article, b=tr_btn, lbl=title_lbl:
                    self._translate_title(a, b, lbl)
            )
            tr_btn.pack(fill="x", pady=(0, 4))

            tr_full_btn = secondary_btn(btn_col, "Перевести", command=None, height=28)
            tr_full_btn.configure(
                command=lambda a=article, b=tr_full_btn:
                    self._translate_article(a, b)
            )
            tr_full_btn.pack(fill="x", pady=(0, 4))

            secondary_btn(btn_col, "Перейти на сайт статьи",
                          command=lambda u=article.url: webbrowser.open(u),
                          height=28).pack(fill="x", pady=(0, 4))

            dl_area = ctk.CTkFrame(btn_col, fg_color="transparent")
            dl_area.pack(fill="x")

            dl_btn = secondary_btn(dl_area, "Загрузить", command=None, height=28)
            dl_btn.configure(
                command=lambda a=article, f=dl_area, b=dl_btn:
                    self._download_article(a, f, b)
            )
            dl_btn.pack(fill="x")

    # ──────────────────────────────────────────────────────────────────────────
    #  Download
    # ──────────────────────────────────────────────────────────────────────────

    def _download_article(self, article: Article,
                          dl_area: ctk.CTkFrame, dl_btn: ctk.CTkButton):
        dl_btn.configure(state="disabled", text="Загрузка...")

        def worker():
            try:
                path = download_article(
                    url=article.url,
                    title=article.title,
                    source=article.source,
                    year=article.year,
                )
                save_downloaded_article(
                    title=article.title,
                    url=article.url,
                    source=article.source,
                    year=article.year,
                    file_path=path,
                    user_id=self._current_user["id"],
                    authors=article.authors,
                )
                ext = Path(path).suffix.lower()
                self.after(0, lambda p=path, e=ext: self._on_download_done(dl_area, p, e))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_download_error(dl_btn, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_download_done(self, dl_area: ctk.CTkFrame, path: str, ext: str):
        for w in dl_area.winfo_children():
            w.destroy()

        secondary_btn(dl_area, "Открыть оригинал",
                      command=lambda p=path: open_document(self.winfo_toplevel(), p),
                      height=26).pack(fill="x", pady=(0, 3))

        if ext == ".pdf":
            txt_btn = secondary_btn(dl_area, "Открыть в TXT", command=None, height=26)
            txt_btn.configure(
                command=lambda p=path, b=txt_btn: self._open_as_txt(p, b))
            txt_btn.pack(fill="x", pady=(0, 3))

        sum_btn = secondary_btn(dl_area, "Сформировать выжимку",
                                command=None, height=26)
        sum_btn.configure(
            command=lambda p=path, b=sum_btn: self._make_summary(p, b))
        sum_btn.pack(fill="x")

        open_document(self.winfo_toplevel(), path)

    def _on_download_error(self, dl_btn: ctk.CTkButton, error: str):
        dl_btn.configure(state="normal", text="Ошибка")
        print(f"[download] {error}", flush=True)

    # ──────────────────────────────────────────────────────────────────────────
    #  PDF → TXT
    # ──────────────────────────────────────────────────────────────────────────

    def _open_as_txt(self, pdf_path: str, btn: ctk.CTkButton):
        btn.configure(state="disabled", text="Конвертирую...")

        def worker():
            try:
                txt_path = save_as_txt(pdf_path)
                self.after(0, lambda p=txt_path: self._on_txt_done(btn, p))
            except Exception as e:
                self.after(0, lambda: btn.configure(state="normal",
                                                    text="Ошибка TXT"))
                print(f"[pdf→txt] {e}", flush=True)

        threading.Thread(target=worker, daemon=True).start()

    def _on_txt_done(self, btn: ctk.CTkButton, path: str):
        btn.configure(state="normal", text="Открыть в TXT",
                      command=lambda p=path: open_document(self.winfo_toplevel(), p))
        open_document(self.winfo_toplevel(), path)

    # ──────────────────────────────────────────────────────────────────────────
    #  Выжимка
    # ──────────────────────────────────────────────────────────────────────────

    def _make_summary(self, file_path: str, btn: ctk.CTkButton):
        if not self._summarizer.is_available():
            btn.configure(text="Ollama недоступна")
            return
        btn.configure(state="disabled", text="Формирую выжимку...")

        def worker():
            try:
                p = Path(file_path)
                text = (pdf_to_txt(file_path)
                        if p.suffix.lower() == ".pdf"
                        else p.read_text(encoding="utf-8"))
                if not text.strip():
                    raise ValueError("Файл не содержит извлекаемого текста")
                summary = self._summarizer.summarize(text)
                out_path = str(p.with_name(p.stem + "_выжимка.txt"))
                Path(out_path).write_text(summary, encoding="utf-8")
                self.after(0, lambda op=out_path: self._on_summary_done(btn, op))
            except Exception as e:
                self.after(0, lambda: btn.configure(state="normal",
                                                    text="Ошибка выжимки"))
                print(f"[summary] {e}", flush=True)

        threading.Thread(target=worker, daemon=True).start()

    def _on_summary_done(self, btn: ctk.CTkButton, path: str):
        btn.configure(state="normal", text="Открыть выжимку",
                      command=lambda p=path: open_document(self.winfo_toplevel(), p))
        open_document(self.winfo_toplevel(), path)

    def _translate_article(self, article: Article, btn: ctk.CTkButton):
        if not self._translator.is_available():
            btn.configure(text="Ollama недоступна")
            return
        btn.configure(state="disabled", text="Перевожу...")

        def worker():
            try:
                parts = [article.title]
                if article.abstract:
                    parts.append(article.abstract)
                text = "\n\n".join(parts)
                translated = self._translator.translate_to_russian(text)
                safe = re.sub(r'[^\w\s-]', '', article.title)[:60].strip()
                out_path = os.path.join(tempfile.gettempdir(), f"{safe}_RU.txt")
                Path(out_path).write_text(translated, encoding="utf-8")
                self.after(0, lambda p=out_path: self._on_article_translation_done(btn, p))
            except Exception as e:
                self.after(0, lambda: btn.configure(state="normal", text="Ошибка перевода"))
                print(f"[translate] {e}", flush=True)

        threading.Thread(target=worker, daemon=True).start()

    def _on_article_translation_done(self, btn: ctk.CTkButton, path: str):
        btn.configure(state="normal", text="Открыть перевод",
                      command=lambda p=path: open_document(self.winfo_toplevel(), p))
        open_document(self.winfo_toplevel(), path)

    def _translate_title(self, article: Article,
                         btn: ctk.CTkButton, lbl: ctk.CTkLabel):
        if not self._translator.is_available():
            btn.configure(text="Ollama недоступна")
            return
        btn.configure(state="disabled", text="Перевод...")

        def worker():
            ru = self._translator.translate_to_russian(article.title)
            self.after(0, lambda: lbl.configure(text=ru))
            self.after(0, lambda: btn.configure(state="normal", text="Переведено"))

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _format_authors(authors: list[str]) -> str:
        if len(authors) <= 3:
            return ", ".join(authors)
        return f"{', '.join(authors[:3])} и ещё {len(authors) - 3}"
