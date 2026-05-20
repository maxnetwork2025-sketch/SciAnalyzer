import os
import shutil
import tkinter as tk
import tkinter.filedialog as fd
from pathlib import Path

import customtkinter as ctk

from core.pdf_handler import PDFHandler
from ui.theme import (
    BG, BG_ALT, BG_DEEP, PAPER, TEXT, TEXT_MUTED, TEXT_GHOST,
    BORDER_SOFT, ACCENT_SOFT,
    font, primary_btn, secondary_btn,
)


def open_document(parent, file_path: str) -> None:
    """Открывает DocumentViewer для PDF/TXT, иначе — os.startfile."""
    ext = Path(file_path).suffix.lower()
    if ext in (".pdf", ".txt"):
        DocumentViewer(parent, file_path)
    else:
        try:
            os.startfile(file_path)
        except Exception as e:
            print(f"[open] {e}", flush=True)


class DocumentViewer(ctk.CTkToplevel):
    _MIN_DPI = 72
    _MAX_DPI = 300
    _DPI_STEP = 25

    def __init__(self, parent, file_path: str):
        super().__init__(parent)
        self._file_path  = file_path
        self._handler    = PDFHandler()
        self._page_count = 0
        self._cur_page   = 0
        self._dpi        = 150
        self._ctk_image  = None          # держим ссылку, чтобы GC не удалил
        self._is_pdf     = Path(file_path).suffix.lower() == ".pdf"

        self.title(f"Просмотр — {Path(file_path).name}")
        self.geometry("1280x900")
        self.minsize(800, 600)
        self.configure(fg_color=BG)
        self.attributes("-topmost", True)

        self._build()
        self._load_file()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(60, self.grab_set)    # небольшая задержка перед grab

    # ──────────────────────────────────────────────────────────────────────────
    #  Layout
    # ──────────────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Топбар ────────────────────────────────────────────────────────
        topbar = ctk.CTkFrame(self, height=46, corner_radius=0, fg_color=BG_ALT)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkFrame(self, height=2, corner_radius=0,
                     fg_color=BORDER_SOFT).pack(fill="x")

        ctk.CTkLabel(
            topbar,
            text=Path(self._file_path).name,
            font=font(13, "bold"),
            text_color=TEXT,
            anchor="w",
        ).pack(side="left", padx=16, fill="y")

        secondary_btn(topbar, "Закрыть ×",
                      command=self._on_close, height=30).pack(
                          side="right", padx=12, pady=8)

        # ── Центральная область ────────────────────────────────────────────
        if self._is_pdf:
            self._scroll = ctk.CTkScrollableFrame(
                self,
                corner_radius=0,
                fg_color=BG_DEEP,
                scrollbar_button_color=BG_DEEP,
                scrollbar_button_hover_color=TEXT_GHOST,
            )
            self._scroll.pack(fill="both", expand=True)
            self._scroll.grid_columnconfigure(0, weight=1)

            self._page_label = ctk.CTkLabel(
                self._scroll, text="", fg_color="transparent"
            )
            self._page_label.grid(row=0, column=0, pady=16)
        else:
            self._textbox = ctk.CTkTextbox(
                self,
                corner_radius=0,
                fg_color=PAPER,
                font=font(13, mono=True),
                text_color=TEXT,
                border_width=0,
                wrap="word",
                activate_scrollbars=True,
            )
            self._textbox.pack(fill="both", expand=True)

        # ── Боттомбар ─────────────────────────────────────────────────────
        ctk.CTkFrame(self, height=2, corner_radius=0,
                     fg_color=BORDER_SOFT).pack(fill="x")
        botbar = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color=BG_ALT)
        botbar.pack(fill="x")
        botbar.pack_propagate(False)

        # Навигация (слева)
        nav = ctk.CTkFrame(botbar, fg_color="transparent")
        nav.pack(side="left", padx=16, fill="y")

        self._prev_btn = primary_btn(nav, "‹ Назад",
                                      command=self._prev_page, height=34)
        self._prev_btn.pack(side="left", pady=9, padx=(0, 8))

        self._page_var = ctk.StringVar(value="—")
        ctk.CTkLabel(
            nav,
            textvariable=self._page_var,
            font=font(13, mono=True),
            text_color=TEXT_MUTED,
            width=90,
            anchor="center",
        ).pack(side="left", pady=9)

        self._next_btn = primary_btn(nav, "Вперёд ›",
                                      command=self._next_page, height=34)
        self._next_btn.pack(side="left", pady=9, padx=(8, 0))

        # Зум (справа)
        zoom = ctk.CTkFrame(botbar, fg_color="transparent")
        zoom.pack(side="right", padx=16, fill="y")

        self._zoom_plus_btn = secondary_btn(zoom, "+",
                                             command=self._zoom_in,
                                             height=34, width=44)
        self._zoom_plus_btn.pack(side="right", pady=9, padx=(4, 0))

        self._zoom_var = ctk.StringVar(value=f"{self._dpi} dpi")
        ctk.CTkLabel(
            zoom,
            textvariable=self._zoom_var,
            font=font(12, mono=True),
            text_color=TEXT_MUTED,
            width=72,
            anchor="center",
        ).pack(side="right", pady=9)

        self._zoom_minus_btn = secondary_btn(zoom, "−",
                                              command=self._zoom_out,
                                              height=34, width=44)
        self._zoom_minus_btn.pack(side="right", pady=9, padx=(0, 4))

        # Для TXT — дизейблим всё что про страницы
        if not self._is_pdf:
            for btn in (self._prev_btn, self._next_btn,
                        self._zoom_minus_btn, self._zoom_plus_btn):
                btn.configure(state="disabled")
            self._page_var.set("TXT")

    # ──────────────────────────────────────────────────────────────────────────
    #  Загрузка
    # ──────────────────────────────────────────────────────────────────────────

    def _load_file(self):
        if self._is_pdf:
            try:
                self._page_count = self._handler.open(self._file_path)
                self._cur_page   = 0
                self._render_page()
            except FileNotFoundError:
                self._show_error("Файл не найден")
            except Exception as e:
                self._show_error(str(e))
        else:
            try:
                text = Path(self._file_path).read_text(
                    encoding="utf-8", errors="replace")
                self._textbox.insert("1.0", text)
                self._textbox.configure(state="disabled")
            except Exception as e:
                self._textbox.insert("1.0", f"Ошибка чтения файла:\n{e}")
                self._textbox.configure(state="disabled")

    # ──────────────────────────────────────────────────────────────────────────
    #  Рендеринг страницы
    # ──────────────────────────────────────────────────────────────────────────

    def _render_page(self):
        if not self._handler.is_open():
            return
        try:
            img = self._handler.get_page_image(self._cur_page, self._dpi)
            self._ctk_image = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=(img.width, img.height),
            )
            self._page_label.configure(image=self._ctk_image, text="")
        except Exception as e:
            self._page_label.configure(image=None,
                                        text=f"Ошибка рендеринга:\n{e}")

        self._page_var.set(f"{self._cur_page + 1} / {self._page_count}")
        self._prev_btn.configure(
            state="normal" if self._cur_page > 0 else "disabled")
        self._next_btn.configure(
            state="normal" if self._cur_page < self._page_count - 1 else "disabled")
        self._zoom_minus_btn.configure(
            state="normal" if self._dpi > self._MIN_DPI else "disabled")
        self._zoom_plus_btn.configure(
            state="normal" if self._dpi < self._MAX_DPI else "disabled")
        self._zoom_var.set(f"{self._dpi} dpi")

        # Прокручиваем к началу страницы
        try:
            self._scroll._parent_canvas.yview_moveto(0)
        except Exception:
            pass

    def _show_error(self, msg: str):
        self._page_label.configure(image=None, text=f"Ошибка: {msg}")
        self._page_var.set("—")
        for btn in (self._prev_btn, self._next_btn,
                    self._zoom_minus_btn, self._zoom_plus_btn):
            btn.configure(state="disabled")

    # ──────────────────────────────────────────────────────────────────────────
    #  Навигация и зум
    # ──────────────────────────────────────────────────────────────────────────

    def _prev_page(self):
        if self._cur_page > 0:
            self._cur_page -= 1
            self._render_page()

    def _next_page(self):
        if self._cur_page < self._page_count - 1:
            self._cur_page += 1
            self._render_page()

    def _zoom_in(self):
        if self._dpi < self._MAX_DPI:
            self._dpi = min(self._dpi + self._DPI_STEP, self._MAX_DPI)
            self._render_page()

    def _zoom_out(self):
        if self._dpi > self._MIN_DPI:
            self._dpi = max(self._dpi - self._DPI_STEP, self._MIN_DPI)
            self._render_page()

    # ──────────────────────────────────────────────────────────────────────────
    #  Горячие клавиши
    # ──────────────────────────────────────────────────────────────────────────

    def _bind_keys(self):
        # Общие
        self.bind("<Escape>",    lambda _: self._on_close())
        self.bind("<Control-s>", lambda _: self._save_file())
        self.bind("<Control-S>", lambda _: self._save_file())

        # PDF: навигация и зум
        self.bind("<Left>",          lambda _: self._prev_page())
        self.bind("<Right>",         lambda _: self._next_page())
        self.bind("<Control-equal>", lambda _: self._zoom_in())
        self.bind("<Control-plus>",  lambda _: self._zoom_in())
        self.bind("<Control-minus>", lambda _: self._zoom_out())

        if self._is_pdf:
            self._attach_pdf_context_menu()
            self.bind("<Control-c>", lambda _: self._copy_page_text())
            self.bind("<Control-C>", lambda _: self._copy_page_text())
        else:
            self._attach_textbox_bindings()

    # ──────────────────────────────────────────────────────────────────────────
    #  Шорткаты и контекстное меню — TXT
    # ──────────────────────────────────────────────────────────────────────────

    def _attach_textbox_bindings(self):
        inner: tk.Text = self._textbox._textbox  # внутренний tk.Text

        def _select_all(event=None):
            inner.tag_add("sel", "1.0", "end")
            inner.mark_set("insert", "1.0")
            inner.see("1.0")
            return "break"

        def _copy(event=None):
            try:
                text = inner.get("sel.first", "sel.last")
                self.clipboard_clear()
                self.clipboard_append(text)
            except tk.TclError:
                pass
            return "break"

        def _show_menu(event):
            has_sel = False
            try:
                inner.index("sel.first")
                has_sel = True
            except tk.TclError:
                pass

            menu = tk.Menu(
                inner, tearoff=0,
                bg=PAPER, fg=TEXT,
                activebackground=ACCENT_SOFT, activeforeground=TEXT,
                font=("Segoe UI", 12), bd=1, relief="solid",
            )
            menu.add_command(
                label="Копировать",
                accelerator="Ctrl+C",
                state="normal" if has_sel else "disabled",
                command=_copy,
            )
            menu.add_separator()
            menu.add_command(
                label="Выделить всё",
                accelerator="Ctrl+A",
                command=_select_all,
            )
            menu.add_separator()
            menu.add_command(
                label="Закрыть",
                accelerator="Esc",
                command=self._on_close,
            )
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        inner.bind("<Button-3>",  _show_menu)
        inner.bind("<Control-a>", _select_all)
        inner.bind("<Control-A>", _select_all)
        inner.bind("<Control-c>", _copy)
        inner.bind("<Control-C>", _copy)

    # ──────────────────────────────────────────────────────────────────────────
    #  Контекстное меню — PDF
    # ──────────────────────────────────────────────────────────────────────────

    def _attach_pdf_context_menu(self):
        def _show_menu(event):
            menu = tk.Menu(
                self, tearoff=0,
                bg=PAPER, fg=TEXT,
                activebackground=ACCENT_SOFT, activeforeground=TEXT,
                font=("Segoe UI", 12), bd=1, relief="solid",
            )
            menu.add_command(
                label="Копировать текст страницы",
                accelerator="Ctrl+C",
                command=self._copy_page_text,
            )
            menu.add_separator()
            menu.add_command(
                label="Закрыть",
                accelerator="Esc",
                command=self._on_close,
            )
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        for widget in (self._page_label, self._scroll):
            widget.bind("<Button-3>", _show_menu)

    def _copy_page_text(self):
        if not self._handler.is_open():
            return
        try:
            text = self._handler.get_page_text(self._cur_page)
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception as e:
            print(f"[copy page] {e}", flush=True)

    # ──────────────────────────────────────────────────────────────────────────
    #  Сохранение файла (Ctrl+S)
    # ──────────────────────────────────────────────────────────────────────────

    def _save_file(self):
        src = Path(self._file_path)
        if self._is_pdf:
            filetypes = [("PDF файлы", "*.pdf"), ("Все файлы", "*.*")]
            ext = ".pdf"
        else:
            filetypes = [("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
            ext = ".txt"

        dst = fd.asksaveasfilename(
            parent=self,
            title="Сохранить копию",
            initialfile=src.name,
            defaultextension=ext,
            filetypes=filetypes,
        )
        if not dst:
            return
        try:
            shutil.copy2(str(src), dst)
        except Exception as e:
            print(f"[save] {e}", flush=True)

    # ──────────────────────────────────────────────────────────────────────────

    def _on_close(self):
        self._handler.close()
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
