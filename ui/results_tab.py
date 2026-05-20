import os
import re
import shutil
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

import customtkinter as ctk
import fitz
import tkinter.filedialog as fd

from core.summarizer import Summarizer
from core.translator import Translator
from core.embedder   import Embedder
from core.downloader import pdf_to_txt, save_as_txt, DOWNLOAD_DIR
from db import get_user_articles, delete_article, search_similar_articles, save_downloaded_article
from ui.document_viewer import open_document
from ui.theme import (
    BG, BG_ALT, BG_DEEP, PAPER, TEXT, TEXT_MUTED, TEXT_GHOST,
    BORDER, BORDER_SOFT, ACCENT, ACCENT_SOFT, DANGER, SUCCESS,
    font, styled_entry, section_label, divider,
    primary_btn, secondary_btn, card_frame, scrollable,
)

_SOURCE_COLORS = {
    "arXiv":              ("#fff3ee", ACCENT,     ACCENT),
    "PubMed":             ("#e8f4ec", "#2e7d52",  "#2e7d52"),
    "Semantic Scholar":   (BG_DEEP,   TEXT_MUTED, TEXT_MUTED),
    "CyberLeninka":       ("#eef2ff", "#3b5bdb",  "#3b5bdb"),
    "SibAC":              ("#fff8e1", "#b45309",  "#b45309"),
    "МолодойУчёный":     ("#fdf4ff", "#7e22ce",  "#7e22ce"),
    "eLibrary":           ("#eff6ff", "#1d4ed8",  "#1d4ed8"),
    "Загружен вручную":   ("#e8f5e9", "#2e7d32",  "#2e7d32"),
}


class LibraryTab(ctk.CTkFrame):
    def __init__(self, parent, current_user: dict):
        super().__init__(parent, fg_color="transparent")
        self._current_user   = current_user
        self._translator     = Translator()
        self._summarizer     = Summarizer()
        self._embedder       = Embedder()
        self._all_articles:  list[dict]        = []
        self._source_vars:   dict[str, ctk.BooleanVar] = {}
        self._semantic_scores: dict[int, float] = {}   # id→score; пусто = фильтр неактивен
        self._build()
        self.after(100, self._load)
        self.after(300, self._check_embed_model)

    # ──────────────────────────────────────────────────────────────────────────
    #  Layout
    # ──────────────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Left panel ─────────────────────────────────────────────────────
        self._left = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color=BG_ALT)
        self._left.pack(side="left", fill="y")
        self._left.pack_propagate(False)
        ctk.CTkFrame(self, width=2, corner_radius=0,
                     fg_color=BORDER_SOFT).pack(side="left", fill="y")

        section_label(self._left, "Фильтр по автору", padx=16, pady=(16, 8))
        self._author_entry = styled_entry(
            self._left, placeholder="Фамилия автора...", height=36)
        self._author_entry.pack(padx=16, fill="x", pady=(0, 12))
        self._author_entry.bind("<KeyRelease>", lambda _: self._apply_filter())

        divider(self._left, padx=16, pady=(0, 10))
        section_label(self._left, "Источники", padx=16, pady=(0, 8))
        self._sources_frame = ctk.CTkFrame(self._left, fg_color="transparent")
        self._sources_frame.pack(fill="x")

        ctk.CTkFrame(self._left, fg_color="transparent").pack(expand=True, fill="both")
        secondary_btn(self._left, "Обновить",
                      command=self._load, height=36).pack(padx=16, fill="x", pady=(0, 8))
        secondary_btn(self._left, "Сбросить фильтры",
                      command=self._reset_filters,
                      height=36).pack(padx=16, fill="x", pady=(0, 12))

        # ── Right panel ────────────────────────────────────────────────────
        right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        section_label(right, "Библиотека · сохранённые статьи",
                      padx=24, pady=(20, 4))
        hdr_row = ctk.CTkFrame(right, fg_color="transparent")
        hdr_row.pack(fill="x", padx=24, pady=(0, 10))
        ctk.CTkLabel(hdr_row, text="Все загруженные статьи",
                     font=font(22, "bold"), text_color=TEXT).pack(side="left")
        self._import_btn = primary_btn(hdr_row, "Импорт из PDF",
                                       command=self._import_pdf, height=36)
        self._import_btn.pack(side="right")

        # ── Semantic search bar ─────────────────────────────────────────────
        sem_card = ctk.CTkFrame(right, fg_color=BG_ALT, corner_radius=4,
                                border_width=2, border_color=BORDER_SOFT)
        sem_card.pack(fill="x", padx=24, pady=(0, 10))

        sem_top = ctk.CTkFrame(sem_card, fg_color="transparent")
        sem_top.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(sem_top, text="СЕМАНТИЧЕСКИЙ ПОИСК",
                     font=font(10, "bold"), text_color=TEXT_GHOST,
                     anchor="w").pack(side="left")

        sem_row = ctk.CTkFrame(sem_card, fg_color="transparent")
        sem_row.pack(fill="x", padx=12, pady=(0, 4))

        self._sem_entry = styled_entry(
            sem_row, placeholder="Найти похожие статьи по смыслу запроса...", height=38)
        self._sem_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._sem_entry.bind("<Return>", lambda _: self._semantic_search())

        self._sem_btn = primary_btn(sem_row, "Найти",
                                    command=self._semantic_search, height=38)
        self._sem_btn.pack(side="left")

        secondary_btn(sem_row, "Сбросить",
                      command=self._clear_semantic, height=38).pack(
                          side="left", padx=(6, 0))

        self._sem_status = ctk.CTkLabel(
            sem_card, text="", font=font(11),
            text_color=TEXT_GHOST, anchor="w")
        self._sem_status.pack(anchor="w", padx=12, pady=(0, 8))

        # ── Keyword filter row ──────────────────────────────────────────────
        search_row = ctk.CTkFrame(right, fg_color="transparent")
        search_row.pack(fill="x", padx=24, pady=(0, 10))
        self._search_entry = styled_entry(
            search_row, placeholder="Фильтр по названию...", height=44)
        self._search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._search_entry.bind("<KeyRelease>", lambda _: self._apply_filter())
        primary_btn(search_row, "Обновить",
                    command=self._load, height=44).pack(side="left")

        divider(right, padx=24, pady=(0, 0))

        self._scroll = scrollable(right)
        self._scroll.pack(fill="both", expand=True, padx=16, pady=8)
        self._show_loading()

    # ──────────────────────────────────────────────────────────────────────────
    #  Data
    # ──────────────────────────────────────────────────────────────────────────

    def _load(self):
        self._show_loading()
        uid = self._current_user["id"]

        def worker():
            rows = get_user_articles(uid)
            self.after(0, lambda r=rows: self._on_loaded(r))

        threading.Thread(target=worker, daemon=True).start()

    def _on_loaded(self, rows: list[dict]):
        self._all_articles = rows
        self._rebuild_source_filters()
        self._apply_filter()

    def _rebuild_source_filters(self):
        for w in self._sources_frame.winfo_children():
            w.destroy()
        self._source_vars.clear()

        sources = sorted({r["source"] or "Неизвестно" for r in self._all_articles})
        for src in sources:
            var = ctk.BooleanVar(value=True)
            self._source_vars[src] = var
            ctk.CTkCheckBox(
                self._sources_frame,
                text=src,
                variable=var,
                font=font(13),
                text_color=TEXT_MUTED,
                fg_color=ACCENT,
                hover_color=ACCENT_SOFT,
                border_color=BORDER,
                border_width=2,
                checkmark_color=PAPER,
                corner_radius=2,
                command=self._apply_filter,
            ).pack(anchor="w", padx=16, pady=3)

    def _apply_filter(self):
        title_q  = self._search_entry.get().strip().lower()
        author_q = self._author_entry.get().strip().lower()
        enabled  = {src for src, var in self._source_vars.items() if var.get()}

        if self._semantic_scores:
            filtered = [
                r for r in self._all_articles
                if r["id"] in self._semantic_scores
                and (not title_q  or title_q  in (r["title"]   or "").lower())
                and (not author_q or author_q in (r["authors"] or "").lower())
                and (not enabled  or (r["source"] or "Неизвестно") in enabled)
            ]
            filtered.sort(key=lambda r: self._semantic_scores.get(r["id"], 0.0),
                          reverse=True)
        else:
            filtered = [
                r for r in self._all_articles
                if (not title_q  or title_q  in (r["title"]   or "").lower())
                and (not author_q or author_q in (r["authors"] or "").lower())
                and (not enabled  or (r["source"] or "Неизвестно") in enabled)
            ]

        self._show_results(filtered)

    def _reset_filters(self):
        self._search_entry.delete(0, "end")
        self._author_entry.delete(0, "end")
        for var in self._source_vars.values():
            var.set(True)
        self._clear_semantic()

    # ──────────────────────────────────────────────────────────────────────────
    #  Semantic search
    # ──────────────────────────────────────────────────────────────────────────

    def _check_embed_model(self):
        def worker():
            if not self._embedder.is_available():
                self.after(0, lambda: self._sem_status.configure(
                    text="Модель недоступна. Установите: ollama pull nomic-embed-text",
                    text_color=TEXT_MUTED,
                ))
        threading.Thread(target=worker, daemon=True).start()

    def _semantic_search(self):
        query = self._sem_entry.get().strip()
        if not query:
            self._clear_semantic()
            return

        self._sem_btn.configure(state="disabled", text="Поиск...")
        self._sem_status.configure(text="Вычисляю эмбеддинг...", text_color=TEXT_MUTED)
        uid = self._current_user["id"]

        def worker():
            try:
                emb     = self._embedder.embed(query)
                results = search_similar_articles(emb, top_k=200, user_id=uid)
                scores  = {r["id"]: r["score"] for r in results}
                self.after(0, lambda s=scores: self._on_semantic_done(s))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_semantic_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_semantic_done(self, scores: dict):
        self._semantic_scores = scores
        self._sem_btn.configure(state="normal", text="Найти")
        if scores:
            self._sem_status.configure(
                text=f"Найдено {len(scores)} похожих статей · отсортировано по релевантности",
                text_color=SUCCESS,
            )
        else:
            self._sem_status.configure(
                text="Нет статей с вычисленными эмбеддингами в библиотеке",
                text_color=TEXT_MUTED,
            )
        self._apply_filter()

    def _on_semantic_error(self, msg: str):
        self._sem_btn.configure(state="normal", text="Найти")
        self._sem_status.configure(
            text=f"Ошибка: {msg}",
            text_color=DANGER,
        )

    def _clear_semantic(self):
        self._semantic_scores = {}
        self._sem_entry.delete(0, "end")
        self._sem_status.configure(text="", text_color=TEXT_GHOST)
        self._apply_filter()

    # ──────────────────────────────────────────────────────────────────────────
    #  Rendering
    # ──────────────────────────────────────────────────────────────────────────

    def _clear(self):
        for w in self._scroll.winfo_children():
            w.destroy()

    def _show_loading(self):
        self._clear()
        wrap = ctk.CTkFrame(self._scroll, fg_color="transparent")
        wrap.pack(expand=True, pady=64)
        ctk.CTkLabel(wrap, text="Загрузка...",
                     font=font(16, "bold"), text_color=TEXT_MUTED).pack(pady=(0, 6))
        ctk.CTkLabel(wrap, text="Читаем базу данных",
                     font=font(13), text_color=TEXT_GHOST).pack()

    def _show_empty(self):
        self._clear()
        wrap = ctk.CTkFrame(self._scroll, fg_color="transparent")
        wrap.pack(expand=True, pady=72)
        if self._semantic_scores:
            ctk.CTkLabel(wrap, text="Нет совпадений",
                         font=font(18, "bold"), text_color=TEXT).pack(pady=(0, 8))
            ctk.CTkLabel(wrap,
                         text="Ни одна сохранённая статья не прошла через фильтры",
                         font=font(13), text_color=TEXT_GHOST, justify="center").pack()
        else:
            ctk.CTkLabel(wrap, text="Библиотека пуста",
                         font=font(18, "bold"), text_color=TEXT).pack(pady=(0, 8))
            ctk.CTkLabel(wrap,
                         text="Загрузите статьи во вкладке «Поиск»\nи они появятся здесь",
                         font=font(13), text_color=TEXT_GHOST, justify="center").pack()

    def _show_results(self, articles: list[dict]):
        self._clear()
        if not articles:
            self._show_empty()
            return

        hdr = ctk.CTkFrame(self._scroll, fg_color="transparent")
        hdr.pack(fill="x", padx=4, pady=(4, 6))
        label = (f"Найдено: {len(articles)} статей · семантический поиск"
                 if self._semantic_scores
                 else f"В библиотеке: {len(articles)} статей")
        ctk.CTkLabel(hdr, text=label,
                     font=font(13, "bold"), text_color=TEXT).pack(side="left")

        for row in articles:
            try:
                score = self._semantic_scores.get(row["id"]) if self._semantic_scores else None
                self._article_card(self._scroll, row, score=score)
            except Exception:
                pass

    def _article_card(self, parent, row: dict, score: float | None = None):
        card = card_frame(parent)
        card.pack(fill="x", padx=4, pady=4)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        # ── Source badge + date + score chip ─────────────────────────────
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x", pady=(0, 6))

        source = row.get("source") or "Неизвестно"
        bg, fg, _ = _SOURCE_COLORS.get(source, (BG_DEEP, TEXT_MUTED, TEXT_MUTED))
        badge = ctk.CTkFrame(top, fg_color=bg, corner_radius=3)
        badge.pack(side="left")
        ctk.CTkLabel(badge, text=source,
                     font=font(10, "bold"), text_color=fg).pack(padx=8, pady=2)

        created_at = row.get("created_at", "")
        if created_at:
            ctk.CTkLabel(top, text=str(created_at)[:10],
                         font=font(11, mono=True),
                         text_color=TEXT_GHOST).pack(side="left", padx=(8, 0))

        if score is not None:
            pct = int(score * 100)
            score_chip = ctk.CTkFrame(top, fg_color=ACCENT_SOFT, corner_radius=3)
            score_chip.pack(side="right")
            ctk.CTkLabel(score_chip, text=f"{pct}%",
                         font=font(11, "bold"), text_color=ACCENT).pack(padx=8, pady=2)

        # ── Title ─────────────────────────────────────────────────────────
        title_lbl = ctk.CTkLabel(inner, text=row.get("title", "—"),
                                  font=font(14, "bold"), text_color=TEXT,
                                  anchor="w", wraplength=640, justify="left")
        title_lbl.pack(fill="x", pady=(0, 4))

        authors_str = row.get("authors") or ""
        if authors_str:
            ctk.CTkLabel(inner, text=authors_str,
                         font=font(12), text_color=TEXT_MUTED,
                         anchor="w").pack(fill="x", pady=(0, 6))

        # ── URL + action buttons ──────────────────────────────────────────
        bot = ctk.CTkFrame(inner, fg_color="transparent")
        bot.pack(fill="x")

        source = row.get("source") or ""
        url    = row.get("url") or ""
        is_manual = source == "Загружен вручную"

        if is_manual:
            ctk.CTkLabel(bot, text="Загружен вручную",
                         font=font(11, mono=True), text_color=TEXT_GHOST,
                         anchor="w").pack(side="left", fill="x", expand=True,
                                          padx=(0, 8))
        elif url:
            ctk.CTkLabel(bot, text=url,
                         font=font(11, mono=True), text_color=TEXT_GHOST,
                         anchor="w").pack(side="left", fill="x", expand=True,
                                          padx=(0, 8))

        btn_col = ctk.CTkFrame(bot, fg_color="transparent")
        btn_col.pack(side="right")

        tr_btn = secondary_btn(btn_col, "Перевести название", command=None, height=28)
        tr_btn.configure(
            command=lambda t=row.get("title", ""), b=tr_btn, lbl=title_lbl:
                self._translate_title(t, b, lbl)
        )
        tr_btn.pack(fill="x", pady=(0, 4))

        tr_full_btn = secondary_btn(btn_col, "Перевести", command=None, height=28)
        tr_full_btn.configure(
            command=lambda r=row, b=tr_full_btn: self._translate_article(r, b)
        )
        tr_full_btn.pack(fill="x", pady=(0, 4))

        if url and not is_manual:
            secondary_btn(btn_col, "Перейти на сайт статьи",
                          command=lambda u=url: webbrowser.open(u),
                          height=28).pack(fill="x", pady=(0, 4))

        file_path = row.get("file_path") or ""
        if file_path and os.path.exists(file_path):
            secondary_btn(btn_col, "Открыть файл",
                          command=lambda p=file_path: open_document(self.winfo_toplevel(), p),
                          height=28).pack(fill="x", pady=(0, 4))

            if Path(file_path).suffix.lower() == ".pdf":
                txt_btn = secondary_btn(btn_col, "Открыть в TXT",
                                        command=None, height=28)
                txt_btn.configure(
                    command=lambda p=file_path, b=txt_btn: self._open_as_txt(p, b))
                txt_btn.pack(fill="x", pady=(0, 4))

            sum_btn = secondary_btn(btn_col, "Сформировать выжимку",
                                    command=None, height=28)
            sum_btn.configure(
                command=lambda p=file_path, b=sum_btn: self._make_summary(p, b))
            sum_btn.pack(fill="x", pady=(0, 4))

        del_btn = secondary_btn(btn_col, "Удалить", command=None, height=28)
        del_btn.configure(
            command=lambda aid=row["id"], c=card: self._delete(aid, c))
        del_btn.pack(fill="x")

    # ──────────────────────────────────────────────────────────────────────────
    #  Actions
    # ──────────────────────────────────────────────────────────────────────────

    def _translate_article(self, row: dict, btn: ctk.CTkButton):
        if not self._translator.is_available():
            btn.configure(text="Ollama недоступна")
            return
        btn.configure(state="disabled", text="Перевожу...")

        file_path = row.get("file_path") or ""
        title     = row.get("title", "")

        def worker():
            try:
                if file_path and os.path.exists(file_path):
                    p = Path(file_path)
                    text = (pdf_to_txt(file_path)
                            if p.suffix.lower() == ".pdf"
                            else p.read_text(encoding="utf-8"))
                    out_path = str(p.with_name(p.stem + "_RU.txt"))
                else:
                    text = title
                    safe = re.sub(r'[^\w\s-]', '', title)[:60].strip()
                    out_path = os.path.join(tempfile.gettempdir(), f"{safe}_RU.txt")
                translated = self._translator.translate_to_russian(text)
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

    def _translate_title(self, title: str, btn: ctk.CTkButton, lbl: ctk.CTkLabel):
        if not self._translator.is_available():
            btn.configure(text="Ollama недоступна")
            return
        btn.configure(state="disabled", text="Перевод...")

        def worker():
            ru = self._translator.translate_to_russian(title)
            self.after(0, lambda: lbl.configure(text=ru))
            self.after(0, lambda: btn.configure(state="normal", text="Переведено"))

        threading.Thread(target=worker, daemon=True).start()

    def _open_as_txt(self, pdf_path: str, btn: ctk.CTkButton):
        btn.configure(state="disabled", text="Конвертирую...")

        def worker():
            try:
                txt_path = save_as_txt(pdf_path)
                self.after(0, lambda p=txt_path: self._on_txt_done(btn, p))
            except Exception as e:
                self.after(0, lambda: btn.configure(state="normal", text="Ошибка TXT"))
                print(f"[pdf→txt] {e}", flush=True)

        threading.Thread(target=worker, daemon=True).start()

    def _on_txt_done(self, btn: ctk.CTkButton, path: str):
        btn.configure(state="normal", text="Открыть в TXT",
                      command=lambda p=path: open_document(self.winfo_toplevel(), p))
        open_document(self.winfo_toplevel(), path)

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
                self.after(0, lambda: btn.configure(state="normal", text="Ошибка выжимки"))
                print(f"[summary] {e}", flush=True)

        threading.Thread(target=worker, daemon=True).start()

    def _on_summary_done(self, btn: ctk.CTkButton, path: str):
        btn.configure(state="normal", text="Открыть выжимку",
                      command=lambda p=path: open_document(self.winfo_toplevel(), p))
        open_document(self.winfo_toplevel(), path)

    def _import_pdf(self):
        path = fd.askopenfilename(
            title="Выберите PDF-файл статьи",
            filetypes=[("PDF файлы", "*.pdf"), ("Все файлы", "*.*")],
        )
        if not path:
            return

        self._import_btn.configure(state="disabled", text="Обработка...")

        def worker():
            try:
                src = Path(path)
                DOWNLOAD_DIR.mkdir(exist_ok=True)
                dest = DOWNLOAD_DIR / src.name
                if dest.exists():
                    dest = DOWNLOAD_DIR / f"{src.stem}_{int(time.time())}{src.suffix}"
                shutil.copy2(str(src), str(dest))

                doc = fitz.open(str(src))
                text = "\n".join(page.get_text() for page in doc)
                doc.close()

                meta = {"title": src.stem, "authors": "", "year": ""}
                if self._summarizer.is_available() and text.strip():
                    try:
                        extracted = self._summarizer.extract_article_metadata(text)
                        if extracted.get("title"):
                            meta = extracted
                    except Exception:
                        pass

                title       = meta.get("title") or src.stem
                authors_str = meta.get("authors") or ""
                year        = meta.get("year") or ""
                authors_list = [a.strip() for a in authors_str.split(",") if a.strip()]

                uid = self._current_user["id"]
                save_downloaded_article(
                    title=title,
                    url=str(dest),
                    source="Загружен вручную",
                    year=year,
                    file_path=str(dest),
                    user_id=uid,
                    authors=authors_list,
                )
                self.after(0, self._on_import_done)
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_import_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_import_done(self):
        self._import_btn.configure(state="normal", text="Импорт из PDF")
        self._load()

    def _on_import_error(self, msg: str):
        self._import_btn.configure(state="normal", text="Ошибка импорта")
        self.after(3000, lambda: self._import_btn.configure(text="Импорт из PDF"))
        print(f"[import_pdf] {msg}", flush=True)

    def _delete(self, article_id: int, card: ctk.CTkFrame):
        try:
            delete_article(article_id)
        except Exception as e:
            print(f"[delete] {e}", flush=True)
            return
        self._all_articles = [a for a in self._all_articles if a["id"] != article_id]
        self._semantic_scores.pop(article_id, None)
        try:
            card.destroy()
        except Exception:
            pass
        self._apply_filter()
