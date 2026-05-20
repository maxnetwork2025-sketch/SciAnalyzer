import threading
import tkinter as tk
import tkinter.filedialog as fd

import customtkinter as ctk

from db import database as db
from core.compare_engine import extract_text, compare_documents
from ui.theme import (
    BG, BG_ALT, BG_DEEP, PAPER, TEXT, TEXT_MUTED, TEXT_GHOST,
    BORDER, BORDER_SOFT, ACCENT, ACCENT_SOFT, DANGER, SUCCESS,
    font, section_label, divider, primary_btn, secondary_btn,
    scrollable, card_frame,
)

_PICK_EXTENSIONS = (
    ("Документы", "*.pdf *.docx *.txt"),
    ("PDF", "*.pdf"),
    ("Word", "*.docx"),
    ("Текст", "*.txt"),
    ("Все файлы", "*.*"),
)


# ──────────────────────────────────────────────────────────────────────────────
#  Library picker dialog
# ──────────────────────────────────────────────────────────────────────────────

class _LibraryPicker(ctk.CTkToplevel):
    """Modal-like window that lets the user pick one article from the library."""

    def __init__(self, parent, articles: list[dict], callback):
        super().__init__(parent)
        self.title("Выбор из библиотеки")
        self.geometry("560x460")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.grab_set()

        self._articles = articles
        self._filtered = articles[:]
        self._callback = callback

        # Search
        top = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        top.pack(fill="x", padx=16, pady=(14, 8))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        entry = ctk.CTkEntry(
            top, textvariable=self._search_var,
            placeholder_text="Поиск по названию...",
            height=36, fg_color=PAPER, border_width=2,
            border_color=BORDER, corner_radius=3,
            font=font(13), text_color=TEXT,
        )
        entry.pack(fill="x")

        # List
        self._list_frame = scrollable(self, fg_color="transparent")
        self._list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._render_list()

    def _on_search(self, *_):
        q = self._search_var.get().strip().lower()
        self._filtered = [
            a for a in self._articles
            if q in a["title"].lower() or q in (a.get("authors") or "").lower()
        ] if q else self._articles[:]
        self._render_list()

    def _render_list(self):
        for w in self._list_frame.winfo_children():
            w.destroy()

        if not self._filtered:
            ctk.CTkLabel(self._list_frame, text="Ничего не найдено",
                         font=font(13), text_color=TEXT_GHOST).pack(pady=20)
            return

        for art in self._filtered:
            row = ctk.CTkFrame(self._list_frame, fg_color=PAPER,
                               corner_radius=3, border_width=2, border_color=BORDER_SOFT)
            row.pack(fill="x", padx=4, pady=3)

            info = ctk.CTkFrame(row, fg_color="transparent", corner_radius=0)
            info.pack(side="left", fill="both", expand=True, padx=10, pady=8)

            title = art["title"][:70] + ("…" if len(art["title"]) > 70 else "")
            ctk.CTkLabel(info, text=title, font=font(12, "bold"),
                         text_color=TEXT, anchor="w", wraplength=380).pack(anchor="w")

            meta = f"{art.get('source') or ''} · {(art.get('authors') or '')[:40]}"
            ctk.CTkLabel(info, text=meta.strip(" ·"), font=font(11),
                         text_color=TEXT_MUTED, anchor="w").pack(anchor="w")

            ctk.CTkButton(
                row, text="Выбрать", width=80, height=32,
                corner_radius=3, font=font(12),
                fg_color=ACCENT, hover_color="#c56844",
                text_color=PAPER, border_width=0,
                command=lambda a=art: self._pick(a),
            ).pack(side="right", padx=10, pady=8)

    def _pick(self, article: dict):
        self._callback(article)
        self.destroy()


# ──────────────────────────────────────────────────────────────────────────────
#  Main tab
# ──────────────────────────────────────────────────────────────────────────────

class CompareTab(ctk.CTkFrame):
    def __init__(self, parent, current_user: dict):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.current_user = current_user

        # _slots[i] = None | {"title": str, "file_path": str|None, "content": str|None}
        self._slots: list[dict | None] = [None, None]

        self._build()

    # ──────────────────────────────────────────────────────────────────────
    #  Layout
    # ──────────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Toolbar ───────────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color=BG_ALT)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)
        divider(self, pady=0)

        ctk.CTkLabel(toolbar, text="Сравнение документов",
                     font=font(15, "bold"), text_color=TEXT).pack(
            side="left", padx=20, pady=14)

        # ── Selector area ─────────────────────────────────────────────────
        sel_area = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        sel_area.pack(fill="x", padx=16, pady=(14, 0))
        sel_area.grid_columnconfigure((0, 2), weight=1)
        sel_area.grid_columnconfigure(1, weight=0, minsize=12)

        self._slot_title_lbls: list[ctk.CTkLabel] = []
        self._slot_sub_lbls:   list[ctk.CTkLabel] = []
        self._slot_clear_btns: list[ctk.CTkButton] = []

        for i, label in enumerate(["Документ А", "Документ Б"]):
            col = 0 if i == 0 else 2
            self._build_slot_card(sel_area, i, label, col)

        # ── Compare button ────────────────────────────────────────────────
        mid = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        mid.pack(fill="x", padx=16, pady=12)

        primary_btn(mid, "Сравнить", height=42,
                    command=self._start_compare).pack(side="left")

        self._status_lbl = ctk.CTkLabel(
            mid, text="", font=font(12), text_color=TEXT_GHOST, anchor="w",
        )
        self._status_lbl.pack(side="left", padx=12)

        divider(self, padx=16)

        # ── Result area ───────────────────────────────────────────────────
        self._result_outer = scrollable(self, fg_color="transparent")
        self._result_outer.pack(fill="both", expand=True, padx=16, pady=12)

        self._show_empty_state()

    def _build_slot_card(self, parent, idx: int, title: str, col: int):
        card = card_frame(parent)
        card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0))
        card.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        hdr.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(hdr, text=title, font=font(13, "bold"),
                     text_color=TEXT, anchor="w").pack(side="left")

        clear_btn = ctk.CTkButton(
            hdr, text="✕", width=24, height=24,
            corner_radius=3, font=font(11),
            fg_color="transparent", hover_color=BG_DEEP,
            text_color=TEXT_MUTED, border_width=0,
            command=lambda i=idx: self._clear_slot(i),
        )
        clear_btn.pack(side="right")
        clear_btn.pack_forget()  # hidden until something is selected
        self._slot_clear_btns.append(clear_btn)

        # Buttons row
        btn_row = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        btn_row.pack(fill="x", padx=14, pady=(0, 6))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        secondary_btn(btn_row, "Из библиотеки", height=34,
                      command=lambda i=idx: self._pick_library(i)).grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        secondary_btn(btn_row, "С диска", height=34,
                      command=lambda i=idx: self._pick_disk(i)).grid(
            row=0, column=1, sticky="ew", padx=(4, 0))

        # Selected item display
        info = ctk.CTkFrame(card, fg_color=BG_ALT, corner_radius=3)
        info.pack(fill="x", padx=14, pady=(0, 12))

        title_lbl = ctk.CTkLabel(
            info, text="Не выбрано", font=font(12),
            text_color=TEXT_GHOST, anchor="w", wraplength=340,
        )
        title_lbl.pack(fill="x", padx=10, pady=(8, 2))

        sub_lbl = ctk.CTkLabel(
            info, text="", font=font(11),
            text_color=TEXT_MUTED, anchor="w",
        )
        sub_lbl.pack(fill="x", padx=10, pady=(0, 8))

        self._slot_title_lbls.append(title_lbl)
        self._slot_sub_lbls.append(sub_lbl)

    # ──────────────────────────────────────────────────────────────────────
    #  Slot selection
    # ──────────────────────────────────────────────────────────────────────

    def _pick_library(self, idx: int):
        articles = db.get_user_articles(self.current_user["id"])
        if not articles:
            self._set_status("Библиотека пуста — сначала добавьте статьи", error=True)
            return

        def on_pick(article: dict):
            self._set_slot(idx, {
                "title":     article["title"],
                "file_path": article.get("file_path") or None,
                "content":   article.get("content") or None,
                "sub":       f"{article.get('source') or ''} · {(article.get('authors') or '')[:40]}".strip(" ·"),
            })

        _LibraryPicker(self, articles, on_pick)

    def _pick_disk(self, idx: int):
        path = fd.askopenfilename(
            title="Выберите документ",
            filetypes=_PICK_EXTENSIONS,
        )
        if not path:
            return
        from pathlib import Path
        name = Path(path).name
        self._set_slot(idx, {
            "title":     name,
            "file_path": path,
            "content":   None,
            "sub":       path,
        })

    def _set_slot(self, idx: int, data: dict):
        self._slots[idx] = data
        self._slot_title_lbls[idx].configure(text=data["title"], text_color=TEXT)
        self._slot_sub_lbls[idx].configure(text=data["sub"][:60])
        self._slot_clear_btns[idx].pack(side="right")
        self._set_status("")

    def _clear_slot(self, idx: int):
        self._slots[idx] = None
        self._slot_title_lbls[idx].configure(text="Не выбрано", text_color=TEXT_GHOST)
        self._slot_sub_lbls[idx].configure(text="")
        self._slot_clear_btns[idx].pack_forget()

    # ──────────────────────────────────────────────────────────────────────
    #  Comparison
    # ──────────────────────────────────────────────────────────────────────

    def _start_compare(self):
        a, b = self._slots
        if not a:
            self._set_status("Выберите Документ А", error=True)
            return
        if not b:
            self._set_status("Выберите Документ Б", error=True)
            return

        self._set_status("Анализируем…  (может занять несколько секунд)")
        self._show_empty_state()

        def worker():
            try:
                text_a = extract_text(a.get("file_path"), a.get("content"))
                text_b = extract_text(b.get("file_path"), b.get("content"))
                if not text_a.strip():
                    self.after(0, lambda: self._set_status("Не удалось извлечь текст из Документа А", error=True))
                    return
                if not text_b.strip():
                    self.after(0, lambda: self._set_status("Не удалось извлечь текст из Документа Б", error=True))
                    return
                result = compare_documents(text_a, text_b)
                self.after(0, lambda r=result: self._show_results(r))
            except ConnectionError:
                self.after(0, lambda: self._set_status(
                    "Ollama недоступна — запустите сервер и модель nomic-embed-text", error=True))
            except Exception as e:
                self.after(0, lambda err=e: self._set_status(f"Ошибка: {err}", error=True))

        threading.Thread(target=worker, daemon=True).start()

    # ──────────────────────────────────────────────────────────────────────
    #  Result display
    # ──────────────────────────────────────────────────────────────────────

    def _clear_results(self):
        for w in self._result_outer.winfo_children():
            w.destroy()

    def _show_empty_state(self):
        self._clear_results()
        wrap = ctk.CTkFrame(self._result_outer, fg_color="transparent")
        wrap.pack(expand=True, pady=48)
        ctk.CTkLabel(wrap, text="Выберите два документа и нажмите «Сравнить»",
                     font=font(16, "bold"), text_color=TEXT).pack(pady=(0, 8))
        ctk.CTkLabel(wrap,
                     text="Сравнение происходит по семантике (эмбеддинги) и ключевым словам",
                     font=font(13), text_color=TEXT_GHOST).pack()

    def _show_results(self, result):
        self._set_status("")
        self._clear_results()

        # ── Similarity score ──────────────────────────────────────────────
        score_card = card_frame(self._result_outer)
        score_card.pack(fill="x", pady=(0, 12))

        score_inner = ctk.CTkFrame(score_card, fg_color="transparent", corner_radius=0)
        score_inner.pack(fill="x", padx=20, pady=16)

        pct = int(result.semantic_score * 100)
        ctk.CTkLabel(score_inner, text="Семантическая схожесть",
                     font=font(13, "bold"), text_color=TEXT, anchor="w").pack(
            side="left")

        bar_wrap = ctk.CTkFrame(score_inner, fg_color="transparent", corner_radius=0)
        bar_wrap.pack(side="right", fill="x", expand=True, padx=(16, 0))

        bar = ctk.CTkProgressBar(
            bar_wrap, height=12, corner_radius=6,
            fg_color=BG_DEEP, progress_color=ACCENT,
        )
        bar.set(result.semantic_score)
        bar.pack(side="left", fill="x", expand=True, pady=3)

        ctk.CTkLabel(bar_wrap, text=f"{pct}%",
                     font=font(14, "bold"), text_color=ACCENT,
                     width=44, anchor="e").pack(side="right")

        # word counts
        wc = ctk.CTkFrame(score_card, fg_color="transparent", corner_radius=0)
        wc.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkLabel(wc, text=f"Документ А: {result.word_count_a} слов",
                     font=font(11), text_color=TEXT_MUTED, anchor="w").pack(side="left")
        ctk.CTkLabel(wc, text=f"Документ Б: {result.word_count_b} слов",
                     font=font(11), text_color=TEXT_MUTED, anchor="e").pack(side="right")

        # ── Keywords section ──────────────────────────────────────────────
        kw_card = card_frame(self._result_outer)
        kw_card.pack(fill="both", expand=True)

        kw_hdr = ctk.CTkFrame(kw_card, fg_color="transparent", corner_radius=0)
        kw_hdr.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(kw_hdr, text="Ключевые слова", font=font(13, "bold"),
                     text_color=TEXT, anchor="w").pack(side="left")

        divider(kw_card, padx=16, pady=0)

        cols_frame = ctk.CTkFrame(kw_card, fg_color="transparent", corner_radius=0)
        cols_frame.pack(fill="both", expand=True, padx=8, pady=(8, 12))
        cols_frame.grid_columnconfigure((0, 1, 2), weight=1)
        cols_frame.grid_rowconfigure(0, weight=1)

        sections = [
            (f"Общие  ({len(result.common_keywords)})", result.common_keywords, ACCENT_SOFT, ACCENT),
            (f"Только А  ({len(result.only_a)})",       result.only_a,          "#e8f4ec",  "#2e7d52"),
            (f"Только Б  ({len(result.only_b)})",       result.only_b,          "#eef2ff",  "#3b5bdb"),
        ]

        for col_idx, (heading, words, chip_bg, chip_fg) in enumerate(sections):
            col = ctk.CTkFrame(cols_frame, fg_color="transparent", corner_radius=0)
            col.grid(row=0, column=col_idx, sticky="nsew", padx=4)

            ctk.CTkLabel(col, text=heading, font=font(11, "bold"),
                         text_color=TEXT_MUTED, anchor="w").pack(
                fill="x", padx=8, pady=(4, 6))

            chips_scroll = scrollable(col, fg_color="transparent", height=220)
            chips_scroll.pack(fill="both", expand=True)

            if not words:
                ctk.CTkLabel(chips_scroll, text="—", font=font(12),
                             text_color=TEXT_GHOST).pack(pady=8)
            else:
                # flow-like layout: pack chips in rows
                row_frame = None
                for i, word in enumerate(words):
                    if i % 3 == 0:
                        row_frame = ctk.CTkFrame(chips_scroll, fg_color="transparent")
                        row_frame.pack(fill="x", padx=4, pady=2)

                    chip = ctk.CTkFrame(row_frame, fg_color=chip_bg,
                                        corner_radius=10, border_width=0)
                    chip.pack(side="left", padx=2)
                    ctk.CTkLabel(chip, text=word, font=font(11),
                                 text_color=chip_fg).pack(padx=8, pady=3)

    # ──────────────────────────────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, error: bool = False):
        color = DANGER if error else TEXT_GHOST
        self._status_lbl.configure(text=msg, text_color=color)
