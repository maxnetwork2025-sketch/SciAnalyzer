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


class DocumentsTab(ctk.CTkFrame):
    def __init__(self, parent, current_user: dict):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.current_user = current_user
        self._selected_template: str | None = None
        self._field_vars: dict[str, tk.StringVar] = {}
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

        # ── Template list header ──────────────────────────────
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

        # ── Templates folder path bar ─────────────────────────
        path_bar = ctk.CTkFrame(left, fg_color=BG, corner_radius=6,
                                border_width=1, border_color=BORDER_SOFT)
        path_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        path_bar.grid_columnconfigure(0, weight=1)

        path_str = str(TEMPLATES_DIR)
        self._path_entry = ctk.CTkEntry(
            path_bar,
            font=font(11, mono=True),
            text_color=TEXT_MUTED,
            fg_color="transparent",
            border_width=0,
            state="normal",
        )
        self._path_entry.insert(0, path_str)
        self._path_entry.configure(state="readonly")
        self._path_entry.grid(row=0, column=0, sticky="ew", padx=(8, 4), pady=6)

        btn_frame = ctk.CTkFrame(path_bar, fg_color="transparent")
        btn_frame.grid(row=0, column=1, padx=(0, 6), pady=4)

        ctk.CTkButton(
            btn_frame, text="Копировать", width=84, height=26,
            font=font(11), corner_radius=4,
            fg_color="transparent", hover_color=BG_DEEP,
            text_color=TEXT_MUTED, border_width=1, border_color=BORDER_SOFT,
            command=self._copy_templates_path,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btn_frame, text="Открыть", width=70, height=26,
            font=font(11), corner_radius=4,
            fg_color="transparent", hover_color=BG_DEEP,
            text_color=TEXT_MUTED, border_width=1, border_color=BORDER_SOFT,
            command=self._open_templates_folder,
        ).pack(side="left")

        ctk.CTkFrame(left, height=1, fg_color=BORDER_SOFT, corner_radius=0).grid(
            row=2, column=0, sticky="sew", padx=16,
        )

        # ── Form area ─────────────────────────────────────────
        form_outer = ctk.CTkFrame(left, fg_color="transparent", corner_radius=0)
        form_outer.grid(row=3, column=0, sticky="nsew")
        form_outer.grid_rowconfigure(1, weight=1)
        form_outer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(form_outer, text="ПОЛЯ ДОКУМЕНТА", font=font(10, "bold"),
                     text_color=TEXT_GHOST, anchor="w").grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        self._form_scroll = scrollable(form_outer, fg_color="transparent")
        self._form_scroll.grid(row=1, column=0, sticky="nsew", padx=8)

        self._placeholder_lbl = ctk.CTkLabel(
            self._form_scroll,
            text="Выберите шаблон из списка",
            font=font(13), text_color=TEXT_GHOST,
        )
        self._placeholder_lbl.pack(pady=24)

        # ── Status label ──────────────────────────────────────
        self._status_lbl = ctk.CTkLabel(
            left, text="", font=font(11), text_color=SUCCESS, anchor="w",
        )
        self._status_lbl.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 0))

        # ── Buttons ───────────────────────────────────────────
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
        self._history_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self._no_history_lbl = ctk.CTkLabel(
            self._history_scroll,
            text="Нет сохранённых записей",
            font=font(13), text_color=TEXT_GHOST,
        )
        self._no_history_lbl.pack(pady=48)

    # ──────────────────────────────────────────────────────────
    #  Template loading & selection
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
                    text=name,
                    height=34,
                    corner_radius=3,
                    font=font(13),
                    anchor="w",
                    fg_color="transparent",
                    text_color=TEXT_MUTED,
                    hover_color=BG_DEEP,
                    border_width=0,
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
    #  Dynamic form
    # ──────────────────────────────────────────────────────────

    def _build_form(self, template_name: str):
        for w in self._form_scroll.winfo_children():
            w.destroy()
        self._field_vars.clear()
        self._status_lbl.configure(text="")

        if not _DOCXTPL_OK:
            ctk.CTkLabel(
                self._form_scroll,
                text="Установите библиотеку:\npip install docxtpl",
                font=font(12), text_color=DANGER, justify="center",
            ).pack(pady=16)
            return

        try:
            tpl = DocxTemplate(TEMPLATES_DIR / f"{template_name}.docx")
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

        for field in fields:
            row = ctk.CTkFrame(self._form_scroll, fg_color="transparent", corner_radius=0)
            row.pack(fill="x", padx=8, pady=(6, 0))

            ctk.CTkLabel(row, text=field, font=font(12, "bold"),
                         text_color=TEXT, anchor="w").pack(fill="x")

            var = tk.StringVar()
            entry = styled_entry(row, placeholder=f"Введите {field}", textvariable=var)
            entry.pack(fill="x", pady=(3, 0))
            self._field_vars[field] = var

    # ──────────────────────────────────────────────────────────
    #  Actions
    # ──────────────────────────────────────────────────────────

    def _collect_fields(self) -> dict | None:
        if not self._selected_template:
            self._show_status("Выберите шаблон", is_error=True)
            return None
        return {k: v.get().strip() for k, v in self._field_vars.items()}

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

    # ──────────────────────────────────────────────────────────
    #  History panel
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

        # ── Header: template name + date ──────────────────────
        hdr = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        hdr.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(hdr, text=rec["template_name"],
                     font=font(13, "bold"), text_color=TEXT, anchor="w").pack(side="left")
        ctk.CTkLabel(hdr, text=str(rec["created_at"])[:16],
                     font=font(11), text_color=TEXT_GHOST, anchor="e").pack(side="right")

        # ── Fields preview ────────────────────────────────────
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

        # ── Actions ───────────────────────────────────────────
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
    #  Helpers
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
