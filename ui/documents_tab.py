import json
import os
import subprocess
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from ui.theme import (
    BG, BG_ALT, BG_DEEP, PAPER, TEXT, TEXT_MUTED, TEXT_GHOST,
    BORDER, BORDER_SOFT, ACCENT, ACCENT_SOFT, ACCENT_HOV, DANGER, SUCCESS,
    font, section_label, divider, primary_btn, secondary_btn,
    scrollable, card_frame, styled_entry,
)
from db import database as db

from core.paths import TEMPLATES_DIR, OUTPUT_DIR

try:
    from docxtpl import DocxTemplate
    _DOCXTPL_OK = True
except ImportError:
    _DOCXTPL_OK = False


# ══════════════════════════════════════════════════════════════════
#  MultiSelectPopup — всплывающее окно выбора элементов списка
# ══════════════════════════════════════════════════════════════════

class MultiSelectPopup(ctk.CTkToplevel):
    """Чекбоксы для выбора нескольких элементов + добавление/удаление."""

    def __init__(self, parent, list_name: str, items: list,
                 current_selected: list, user_id: int,
                 on_confirm=None, on_items_changed=None):
        super().__init__(parent)
        self._list_name        = list_name
        self._items            = items[:]
        self._user_id          = user_id
        self._on_confirm       = on_confirm
        self._on_items_changed = on_items_changed

        self.title(f"Выбор: {list_name}")
        self.geometry("380x520")
        self.minsize(320, 400)
        self.resizable(True, True)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.configure(fg_color=BG)

        self._check_vars: dict[str, tk.BooleanVar] = {}
        for item in items:
            self._check_vars[item] = tk.BooleanVar(value=item in current_selected)

        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Заголовок ─────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text=self._list_name,
                     font=font(14, "bold"), text_color=TEXT, anchor="w").grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text="Выберите один или несколько",
                     font=font(11), text_color=TEXT_GHOST, anchor="w").grid(
            row=1, column=0, sticky="w")

        # ── Область с чекбоксами ──────────────────────────────
        self._scroll = scrollable(self, fg_color="transparent")
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self._render_checkboxes()

        # ── Добавить новый элемент ────────────────────────────
        add_frame = ctk.CTkFrame(self, fg_color=BG_ALT, corner_radius=0)
        add_frame.grid(row=2, column=0, sticky="ew")
        add_frame.grid_columnconfigure(0, weight=1)

        self._new_entry = styled_entry(add_frame, "Новый элемент...")
        self._new_entry.grid(row=0, column=0, sticky="ew", padx=(12, 4), pady=10)
        self._new_entry.bind("<Return>", lambda _: self._add_item())

        secondary_btn(add_frame, "+ Добавить", height=32,
                      command=self._add_item).grid(row=0, column=1, padx=(0, 12), pady=10)

        # ── Кнопки подтверждения ──────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 14))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        secondary_btn(btn_row, "Отмена", command=self.destroy).grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        primary_btn(btn_row, "Готово", command=self._confirm).grid(
            row=0, column=1, sticky="ew", padx=(4, 0))

    def _render_checkboxes(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        if not self._items:
            ctk.CTkLabel(
                self._scroll,
                text="Список пуст.\nДобавьте элемент ниже.",
                font=font(12), text_color=TEXT_GHOST, justify="center",
            ).pack(pady=24)
            return

        for item in self._items:
            if item not in self._check_vars:
                self._check_vars[item] = tk.BooleanVar(value=False)

            row = ctk.CTkFrame(self._scroll, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=2)
            row.grid_columnconfigure(0, weight=1)

            ctk.CTkCheckBox(
                row, text=item,
                variable=self._check_vars[item],
                font=font(12), text_color=TEXT,
                fg_color=ACCENT, hover_color=ACCENT_HOV,
                checkmark_color=BG, corner_radius=3,
            ).grid(row=0, column=0, sticky="w", padx=8)

            ctk.CTkButton(
                row, text="✕", width=24, height=24,
                fg_color="transparent", hover_color=BG_DEEP,
                text_color=TEXT_GHOST, border_width=0,
                font=font(10), corner_radius=3,
                command=lambda i=item: self._delete_item(i),
            ).grid(row=0, column=1, padx=(0, 4))

    def _add_item(self):
        value = self._new_entry.get().strip()
        if not value or value in self._items:
            return
        db.add_doc_list_item(self._list_name, value, self._user_id)
        self._items.append(value)
        self._check_vars[value] = tk.BooleanVar(value=True)
        self._new_entry.delete(0, "end")
        self._render_checkboxes()
        if self._on_items_changed:
            self._on_items_changed(self._list_name, self._items)

    def _delete_item(self, item: str):
        db.delete_doc_list_item(self._list_name, item, self._user_id)
        self._items.remove(item)
        self._check_vars.pop(item, None)
        self._render_checkboxes()
        if self._on_items_changed:
            self._on_items_changed(self._list_name, self._items)

    def _confirm(self):
        selected = [i for i in self._items
                    if self._check_vars.get(i, tk.BooleanVar()).get()]
        if self._on_confirm:
            self._on_confirm(selected, self._items)
        self.destroy()


# ══════════════════════════════════════════════════════════════════
#  MultiSelectWidget — поле формы с мульти-выбором из списка
# ══════════════════════════════════════════════════════════════════

class MultiSelectWidget(ctk.CTkFrame):
    """Строка формы: показывает выбранное, кнопка открывает MultiSelectPopup."""

    def __init__(self, parent, list_name: str, items: list,
                 user_id: int, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._list_name = list_name
        self._items     = items[:]
        self._user_id   = user_id
        self._selected: list = []
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        wrap = ctk.CTkFrame(self, fg_color=PAPER, corner_radius=3,
                            border_width=1, border_color=BORDER_SOFT)
        wrap.grid(row=0, column=0, sticky="ew")
        wrap.grid_columnconfigure(0, weight=1)

        self._lbl = ctk.CTkLabel(
            wrap, text="Ничего не выбрано",
            font=font(12), text_color=TEXT_GHOST, anchor="w",
        )
        self._lbl.grid(row=0, column=0, sticky="ew", padx=(10, 4), pady=6)

        secondary_btn(wrap, "Выбрать ▾", height=28,
                      command=self._open).grid(row=0, column=1, padx=(0, 4), pady=4)

    def _open(self):
        MultiSelectPopup(
            self, self._list_name, self._items, self._selected, self._user_id,
            on_confirm=self._on_confirm,
            on_items_changed=lambda _n, items: setattr(self, "_items", items),
        )

    def _on_confirm(self, selected: list, items: list):
        self._selected = selected
        self._items    = items
        if selected:
            self._lbl.configure(text=", ".join(selected), text_color=TEXT)
        else:
            self._lbl.configure(text="Ничего не выбрано", text_color=TEXT_GHOST)

    def get(self) -> str:
        return ", ".join(self._selected)


# ══════════════════════════════════════════════════════════════════
#  EditListsDialog — управление всеми пользовательскими списками
# ══════════════════════════════════════════════════════════════════

class EditListsDialog(ctk.CTkToplevel):
    """Диалог создания, редактирования и удаления списков значений."""

    def __init__(self, parent, user_id: int, on_close=None):
        super().__init__(parent)
        self._user_id  = user_id
        self._on_close = on_close

        self.title("Редактор списков")
        self.geometry("640x560")
        self.minsize(560, 440)
        self.resizable(True, True)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._selected_list: str | None = None
        self._build()
        self._load_lists()

    def _build(self):
        self.grid_columnconfigure(0, weight=0, minsize=200)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Левая панель: список имён ──────────────────────────
        left = ctk.CTkFrame(self, fg_color=BG_ALT, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        lhdr = ctk.CTkFrame(left, fg_color="transparent")
        lhdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        lhdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(lhdr, text="СПИСКИ", font=font(10, "bold"),
                     text_color=TEXT_GHOST, anchor="w").grid(row=0, column=0, sticky="w")

        self._list_scroll = scrollable(left, fg_color="transparent")
        self._list_scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)

        # Создать новый список
        new_frame = ctk.CTkFrame(left, fg_color="transparent")
        new_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 10))
        new_frame.grid_columnconfigure(0, weight=1)

        self._new_list_entry = styled_entry(new_frame, "Имя нового списка")
        self._new_list_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._new_list_entry.bind("<Return>", lambda _: self._create_list())

        secondary_btn(new_frame, "+", width=32, height=32,
                      command=self._create_list).grid(row=0, column=1)

        # ── Разделитель ───────────────────────────────────────
        ctk.CTkFrame(self, width=1, fg_color=BORDER_SOFT,
                     corner_radius=0).grid(row=0, column=1, sticky="ns")

        # ── Правая панель: элементы выбранного списка ─────────
        right = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        right.grid(row=0, column=2, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self._items_title = ctk.CTkLabel(
            right, text="Выберите список", font=font(13, "bold"),
            text_color=TEXT_GHOST, anchor="w",
        )
        self._items_title.grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        self._items_scroll = scrollable(right, fg_color="transparent")
        self._items_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)

        add_row = ctk.CTkFrame(right, fg_color=BG_ALT, corner_radius=0)
        add_row.grid(row=2, column=0, sticky="ew")
        add_row.grid_columnconfigure(0, weight=1)

        self._add_item_entry = styled_entry(add_row, "Новый элемент...")
        self._add_item_entry.grid(row=0, column=0, sticky="ew",
                                   padx=(12, 4), pady=10)
        self._add_item_entry.bind("<Return>", lambda _: self._add_item())

        secondary_btn(add_row, "+ Добавить", height=32,
                      command=self._add_item).grid(row=0, column=1,
                                                    padx=(0, 12), pady=10)

    # ── Загрузка/перерисовка списков ──────────────────────────

    def _load_lists(self):
        for w in self._list_scroll.winfo_children():
            w.destroy()

        names = db.get_doc_list_names(self._user_id)
        if not names:
            ctk.CTkLabel(
                self._list_scroll,
                text="Нет списков.\nСоздайте первый.",
                font=font(12), text_color=TEXT_GHOST, justify="center",
            ).pack(pady=16)
            return

        for name in names:
            is_active = name == self._selected_list
            row = ctk.CTkFrame(self._list_scroll, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=2)
            row.grid_columnconfigure(0, weight=1)

            ctk.CTkButton(
                row, text=name, anchor="w", height=32, corner_radius=3,
                font=font(12, "bold" if is_active else "normal"),
                fg_color=ACCENT_SOFT if is_active else "transparent",
                text_color=ACCENT if is_active else TEXT_MUTED,
                hover_color=BG_DEEP, border_width=0,
                command=lambda n=name: self._select_list(n),
            ).grid(row=0, column=0, sticky="ew")

            ctk.CTkButton(
                row, text="✕", width=24, height=24,
                fg_color="transparent", hover_color=BG_DEEP,
                text_color=TEXT_GHOST, border_width=0,
                font=font(10), corner_radius=3,
                command=lambda n=name: self._delete_list(n),
            ).grid(row=0, column=1, padx=(0, 2))

        if self._selected_list and self._selected_list in names:
            self._load_items()

    def _select_list(self, name: str):
        self._selected_list = name
        self._load_lists()
        self._load_items()

    def _load_items(self):
        for w in self._items_scroll.winfo_children():
            w.destroy()

        if not self._selected_list:
            return

        self._items_title.configure(
            text=self._selected_list, text_color=TEXT)

        items = db.get_doc_list_items(self._selected_list, self._user_id)
        if not items:
            ctk.CTkLabel(
                self._items_scroll,
                text="Список пуст.\nДобавьте элементы.",
                font=font(12), text_color=TEXT_GHOST, justify="center",
            ).pack(pady=16)
            return

        for item in items:
            row = ctk.CTkFrame(self._items_scroll, fg_color=PAPER,
                               corner_radius=4, border_width=1,
                               border_color=BORDER_SOFT)
            row.pack(fill="x", padx=6, pady=3)
            row.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(row, text=item, font=font(12), text_color=TEXT,
                         anchor="w").grid(row=0, column=0, sticky="ew",
                                          padx=12, pady=6)

            ctk.CTkButton(
                row, text="Удалить", width=64, height=24,
                fg_color="transparent", hover_color=BG_DEEP,
                text_color=DANGER, border_width=1, border_color=DANGER,
                font=font(10), corner_radius=3,
                command=lambda i=item: self._remove_item(i),
            ).grid(row=0, column=1, padx=(0, 8), pady=4)

    # ── Действия ──────────────────────────────────────────────

    def _create_list(self):
        name = self._new_list_entry.get().strip()
        if not name:
            return
        # Список создаётся добавлением первого элемента-заглушки, который пользователь потом заменит
        self._selected_list = name
        self._new_list_entry.delete(0, "end")
        self._load_lists()
        self._load_items()

    def _add_item(self):
        if not self._selected_list:
            return
        value = self._add_item_entry.get().strip()
        if not value:
            return
        db.add_doc_list_item(self._selected_list, value, self._user_id)
        self._add_item_entry.delete(0, "end")
        self._load_items()

    def _remove_item(self, item: str):
        if not self._selected_list:
            return
        db.delete_doc_list_item(self._selected_list, item, self._user_id)
        self._load_items()

    def _delete_list(self, name: str):
        db.delete_doc_list(name, self._user_id)
        if self._selected_list == name:
            self._selected_list = None
            self._items_title.configure(text="Выберите список",
                                        text_color=TEXT_GHOST)
            for w in self._items_scroll.winfo_children():
                w.destroy()
        self._load_lists()

    def _close(self):
        if self._on_close:
            self._on_close()
        self.destroy()


# ══════════════════════════════════════════════════════════════════
#  DocumentsTab
# ══════════════════════════════════════════════════════════════════

class DocumentsTab(ctk.CTkFrame):
    def __init__(self, parent, current_user: dict):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.current_user = current_user
        self._selected_template: str | None = None
        # значение: tk.StringVar или MultiSelectWidget
        self._field_widgets: dict = {}
        self._template_btns: dict[str, ctk.CTkButton] = {}

        self.grid_columnconfigure(0, weight=0, minsize=400)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_left()
        self._build_sep()
        self._build_right()
        self._load_templates()

    # ──────────────────────────────────────────────────────────
    #  Left panel
    # ──────────────────────────────────────────────────────────

    def _build_left(self):
        left = ctk.CTkFrame(self, fg_color=BG_ALT, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_rowconfigure(3, weight=1)
        left.grid_columnconfigure(0, weight=1)
        self._left = left

        # ── Заголовок списка шаблонов ────────────────────────
        hdr = ctk.CTkFrame(left, fg_color="transparent", corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text="ШАБЛОНЫ", font=font(10, "bold"),
                     text_color=TEXT_GHOST, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            hdr, text="⟳", width=26, height=26, corner_radius=3,
            font=font(13), fg_color="transparent", hover_color=BG_DEEP,
            text_color=TEXT_MUTED, border_width=0,
            command=self._load_templates,
        ).grid(row=0, column=1)

        self._tpl_scroll = scrollable(left, height=160, fg_color="transparent")
        self._tpl_scroll.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))

        # ── Путь к папке шаблонов ─────────────────────────────
        path_bar = ctk.CTkFrame(left, fg_color=BG, corner_radius=6,
                                border_width=1, border_color=BORDER_SOFT)
        path_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        path_bar.grid_columnconfigure(0, weight=1)

        self._path_entry = ctk.CTkEntry(
            path_bar, font=font(11, mono=True), text_color=TEXT_MUTED,
            fg_color="transparent", border_width=0, state="normal",
        )
        self._path_entry.insert(0, str(TEMPLATES_DIR))
        self._path_entry.configure(state="readonly")
        self._path_entry.grid(row=0, column=0, sticky="ew", padx=(8, 4), pady=6)

        btn_frame = ctk.CTkFrame(path_bar, fg_color="transparent")
        btn_frame.grid(row=0, column=1, padx=(0, 6), pady=4)

        ctk.CTkButton(
            btn_frame, text="Копировать", width=84, height=26,
            font=font(11), corner_radius=4, fg_color="transparent",
            hover_color=BG_DEEP, text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER_SOFT,
            command=self._copy_templates_path,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btn_frame, text="Открыть", width=70, height=26,
            font=font(11), corner_radius=4, fg_color="transparent",
            hover_color=BG_DEEP, text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER_SOFT,
            command=self._open_templates_folder,
        ).pack(side="left")

        ctk.CTkFrame(left, height=1, fg_color=BORDER_SOFT,
                     corner_radius=0).grid(row=2, column=0, sticky="sew", padx=16)

        # ── Область формы ────────────────────────────────────
        form_outer = ctk.CTkFrame(left, fg_color="transparent", corner_radius=0)
        form_outer.grid(row=3, column=0, sticky="nsew")
        form_outer.grid_rowconfigure(1, weight=1)
        form_outer.grid_columnconfigure(0, weight=1)

        # Заголовок формы + кнопка редактирования списков
        form_hdr = ctk.CTkFrame(form_outer, fg_color="transparent")
        form_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        form_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(form_hdr, text="ПОЛЯ ДОКУМЕНТА", font=font(10, "bold"),
                     text_color=TEXT_GHOST, anchor="w").grid(row=0, column=0, sticky="w")

        secondary_btn(
            form_hdr, "Редактировать списки", height=26,
            command=self._open_edit_lists,
        ).grid(row=0, column=1)

        self._form_scroll = scrollable(form_outer, fg_color="transparent")
        self._form_scroll.grid(row=1, column=0, sticky="nsew", padx=8)

        self._placeholder_lbl = ctk.CTkLabel(
            self._form_scroll,
            text="Выберите шаблон из списка",
            font=font(13), text_color=TEXT_GHOST,
        )
        self._placeholder_lbl.pack(pady=24)

        # ── Статус ────────────────────────────────────────────
        self._status_lbl = ctk.CTkLabel(
            left, text="", font=font(11), text_color=SUCCESS, anchor="w",
        )
        self._status_lbl.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 0))

        # ── Кнопки действий ───────────────────────────────────
        btn_row = ctk.CTkFrame(left, fg_color="transparent", corner_radius=0)
        btn_row.grid(row=5, column=0, sticky="ew", padx=12, pady=12)
        btn_row.grid_columnconfigure((0, 1), weight=1)

        secondary_btn(btn_row, "Сохранить в БД",
                      command=self._save_to_db, height=38).grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        primary_btn(btn_row, "Создать документ",
                    command=self._create_document, height=38).grid(
            row=0, column=1, sticky="ew", padx=(4, 0))

    def _build_sep(self):
        ctk.CTkFrame(self, width=2, fg_color=BORDER_SOFT, corner_radius=0).grid(
            row=0, column=1, sticky="ns",
        )

    # ──────────────────────────────────────────────────────────
    #  Right panel
    # ──────────────────────────────────────────────────────────

    def _build_right(self):
        right = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        right.grid(row=0, column=2, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="ИСТОРИЯ ЗАПОЛНЕНИЙ", font=font(10, "bold"),
                     text_color=TEXT_GHOST, anchor="w").grid(
            row=0, column=0, sticky="w", padx=20, pady=(14, 4))

        self._history_scroll = scrollable(right, fg_color="transparent")
        self._history_scroll.grid(row=1, column=0, sticky="nsew",
                                   padx=12, pady=(0, 12))

        ctk.CTkLabel(
            self._history_scroll,
            text="Нет сохранённых записей",
            font=font(13), text_color=TEXT_GHOST,
        ).pack(pady=48)

    # ──────────────────────────────────────────────────────────
    #  Загрузка шаблонов
    # ──────────────────────────────────────────────────────────

    def _load_templates(self):
        for w in self._tpl_scroll.winfo_children():
            w.destroy()
        self._template_btns.clear()

        templates = sorted(TEMPLATES_DIR.glob("*.docx")) if TEMPLATES_DIR.exists() else []

        if not templates:
            ctk.CTkLabel(
                self._tpl_scroll,
                text="Нет шаблонов в папке\nШаблоныДокументов/",
                font=font(12), text_color=TEXT_GHOST, justify="center",
            ).pack(pady=12)
        else:
            for tpl_path in templates:
                name = tpl_path.stem
                btn = ctk.CTkButton(
                    self._tpl_scroll,
                    text=name, height=34, corner_radius=3,
                    font=font(13), anchor="w",
                    fg_color="transparent", text_color=TEXT_MUTED,
                    hover_color=BG_DEEP, border_width=0,
                    command=lambda n=name: self._select_template(n),
                )
                btn.pack(fill="x", padx=4, pady=2)
                self._template_btns[name] = btn

        self._load_history()

    def _select_template(self, name: str):
        self._selected_template = name
        for k, b in self._template_btns.items():
            active = k == name
            b.configure(
                fg_color=ACCENT_SOFT if active else "transparent",
                text_color=ACCENT if active else TEXT_MUTED,
                font=font(13, "bold" if active else "normal"),
            )
        self._build_form(name)

    # ──────────────────────────────────────────────────────────
    #  Динамическая форма
    # ──────────────────────────────────────────────────────────

    def _build_form(self, template_name: str):
        for w in self._form_scroll.winfo_children():
            w.destroy()
        self._field_widgets.clear()
        self._status_lbl.configure(text="")

        if not _DOCXTPL_OK:
            ctk.CTkLabel(
                self._form_scroll,
                text="Установите библиотеку:\npip install docxtpl",
                font=font(12), text_color=DANGER, justify="center",
            ).pack(pady=16)
            return

        try:
            tpl    = DocxTemplate(TEMPLATES_DIR / f"{template_name}.docx")
            fields = sorted(tpl.get_undeclared_template_variables())
        except Exception as e:
            ctk.CTkLabel(
                self._form_scroll,
                text=f"Ошибка чтения шаблона:\n{e}",
                font=font(11), text_color=DANGER, justify="center",
            ).pack(pady=12)
            return

        if not fields:
            ctk.CTkLabel(
                self._form_scroll,
                text="В шаблоне нет маркеров {{...}}\nДобавьте их в .docx файл",
                font=font(12), text_color=TEXT_GHOST, justify="center",
            ).pack(pady=20)
            return

        uid        = self.current_user["id"]
        list_names = set(db.get_doc_list_names(uid))

        for field in fields:
            row = ctk.CTkFrame(self._form_scroll, fg_color="transparent",
                               corner_radius=0)
            row.pack(fill="x", padx=8, pady=(6, 0))

            # Заголовок поля: имя + тег «из списка» если есть совпадение
            lbl_row = ctk.CTkFrame(row, fg_color="transparent")
            lbl_row.pack(fill="x")

            ctk.CTkLabel(lbl_row, text=field, font=font(12, "bold"),
                         text_color=TEXT, anchor="w").pack(side="left")

            if field in list_names:
                ctk.CTkLabel(lbl_row, text="  из списка", font=font(10),
                             text_color=ACCENT, anchor="w").pack(side="left")

            # Виджет ввода
            if field in list_names:
                items  = db.get_doc_list_items(field, uid)
                widget = MultiSelectWidget(row, list_name=field,
                                           items=items, user_id=uid)
                widget.pack(fill="x", pady=(3, 0))
                self._field_widgets[field] = widget
            else:
                var   = tk.StringVar()
                entry = styled_entry(row, placeholder=f"Введите {field}",
                                     textvariable=var)
                entry.pack(fill="x", pady=(3, 0))
                self._field_widgets[field] = var

    # ──────────────────────────────────────────────────────────
    #  Действия
    # ──────────────────────────────────────────────────────────

    def _collect_fields(self) -> dict | None:
        if not self._selected_template:
            self._show_status("Выберите шаблон", is_error=True)
            return None
        result = {}
        for k, widget in self._field_widgets.items():
            if isinstance(widget, tk.StringVar):
                result[k] = widget.get().strip()
            else:
                result[k] = widget.get()
        return result

    def _save_to_db(self):
        fields = self._collect_fields()
        if fields is None:
            return
        db.save_document_record(
            template_name=self._selected_template,
            fields=fields,
            output_path=None,
            user_id=self.current_user["id"],
        )
        self._load_history()
        self._show_status("Данные сохранены в БД")

    def _create_document(self):
        fields = self._collect_fields()
        if fields is None:
            return

        if not _DOCXTPL_OK:
            self._show_status("Установите: pip install docxtpl", is_error=True)
            return

        OUTPUT_DIR.mkdir(exist_ok=True)

        from datetime import datetime
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_name = f"{self._selected_template}_{ts}.docx"
        out_path = OUTPUT_DIR / out_name

        try:
            tpl = DocxTemplate(TEMPLATES_DIR / f"{self._selected_template}.docx")
            tpl.render(fields)
            tpl.save(out_path)
        except Exception as e:
            self._show_status(f"Ошибка создания: {e}", is_error=True)
            return

        db.save_document_record(
            template_name=self._selected_template,
            fields=fields,
            output_path=str(out_path),
            user_id=self.current_user["id"],
        )
        self._load_history()
        self._show_status(f"Создан: {out_name}")

    def _open_edit_lists(self):
        """Открывает диалог управления списками и перестраивает форму после закрытия."""
        def on_close():
            if self._selected_template:
                self._build_form(self._selected_template)
        EditListsDialog(self, user_id=self.current_user["id"], on_close=on_close)

    # ──────────────────────────────────────────────────────────
    #  История
    # ──────────────────────────────────────────────────────────

    def _load_history(self):
        for w in self._history_scroll.winfo_children():
            w.destroy()

        records = db.get_document_records(user_id=self.current_user["id"])

        if not records:
            ctk.CTkLabel(
                self._history_scroll,
                text="Нет сохранённых записей",
                font=font(13), text_color=TEXT_GHOST,
            ).pack(pady=48)
            return

        for rec in records:
            self._build_record_card(rec)

    def _build_record_card(self, rec: dict):
        card = card_frame(self._history_scroll)
        card.pack(fill="x", padx=6, pady=6)

        hdr = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(hdr, text=rec["template_name"],
                     font=font(13, "bold"), text_color=TEXT, anchor="w").pack(side="left")
        ctk.CTkLabel(hdr, text=str(rec["created_at"])[:16],
                     font=font(11), text_color=TEXT_GHOST, anchor="e").pack(side="right")

        try:
            fields: dict = json.loads(rec["fields_json"])
        except Exception:
            fields = {}

        for k, v in list(fields.items())[:4]:
            row = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
            row.pack(fill="x", padx=12, pady=1)
            ctk.CTkLabel(row, text=f"{k}:", font=font(11),
                         text_color=TEXT_MUTED, anchor="w", width=130).pack(side="left")
            ctk.CTkLabel(row, text=v or "—", font=font(11),
                         text_color=TEXT, anchor="w").pack(side="left", padx=(4, 0))

        acts = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        acts.pack(fill="x", padx=12, pady=(8, 10))

        out = rec.get("output_path")
        if out and Path(out).exists():
            secondary_btn(acts, "Открыть файл", height=30,
                          command=lambda p=out: self._open_file(p)).pack(
                side="left", padx=(0, 6))

        secondary_btn(acts, "Удалить", height=30,
                      command=lambda rid=rec["id"]: self._delete_record(rid)).pack(
            side="left")

    # ──────────────────────────────────────────────────────────
    #  Утилиты
    # ──────────────────────────────────────────────────────────

    def _copy_templates_path(self):
        self.clipboard_clear()
        self.clipboard_append(str(TEMPLATES_DIR))
        self._show_status("Путь скопирован в буфер обмена")

    def _open_templates_folder(self):
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(TEMPLATES_DIR))
        except Exception:
            subprocess.run(["explorer", str(TEMPLATES_DIR)], check=False)

    def _open_file(self, path: str):
        try:
            os.startfile(path)
        except Exception:
            subprocess.run(["explorer", "/select,", path], check=False)

    def _delete_record(self, record_id: int):
        db.delete_document_record(record_id)
        self._load_history()

    def _show_status(self, msg: str, is_error: bool = False):
        color = DANGER if is_error else SUCCESS
        self._status_lbl.configure(text=msg, text_color=color)
        self.after(4000, lambda: self._status_lbl.configure(text=""))
