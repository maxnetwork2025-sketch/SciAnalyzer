import tkinter as tk
import customtkinter as ctk

# ── Palette ───────────────────────────────────────────────────────────────────
BG          = "#fbf8f3"   # warm cream — main window background
BG_ALT      = "#f3eee4"   # topbar, tab bar, left filter panels
BG_DEEP     = "#e9e3d6"   # table headers, section dividers
PAPER       = "#ffffff"   # cards, input fields

TEXT        = "#1f1d1a"   # primary text
TEXT_MUTED  = "#4a4640"   # secondary / subdued
TEXT_GHOST  = "#b7b1a3"   # placeholders, labels, muted hints

BORDER      = "#1f1d1a"   # all borders (spec: 1.75px → use 2 in CTk)
BORDER_W    = 2
BORDER_SOFT = "#d4cfc6"   # internal dividers, subtle borders

ACCENT      = "#d97757"   # warm orange
ACCENT_SOFT = "#f0e6df"   # light orange tint for chips / tag backgrounds
ACCENT_HOV  = "#c56844"   # hover state for accent buttons

SUCCESS     = "#4a8c6a"   # ✓ requirement met
WARNING     = "#c8960a"
DANGER      = "#cc3333"   # error text

# ── Fonts ─────────────────────────────────────────────────────────────────────
# Inter → Segoe UI (always available on Windows); JetBrains Mono → Consolas
_SANS = "Segoe UI"
_MONO = "Consolas"


def font(size: int = 14, weight: str = "normal", mono: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=(_MONO if mono else _SANS), size=size, weight=weight)


# ── Reusable widget helpers ───────────────────────────────────────────────────

def section_label(parent, text: str, **pack_kw) -> ctk.CTkLabel:
    """UPPERCASE section header label (10 px, ghost color)."""
    lbl = ctk.CTkLabel(parent, text=text.upper(),
                       font=font(10, "bold"), text_color=TEXT_GHOST, anchor="w")
    lbl.pack(**pack_kw)
    return lbl


def divider(parent, **pack_kw):
    """Thin horizontal separator line."""
    ctk.CTkFrame(parent, height=2, corner_radius=0,
                 fg_color=BORDER_SOFT).pack(fill="x", **pack_kw)


def primary_btn(parent, text: str, command=None, height: int = 44, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent, text=text, height=height, command=command,
        font=font(14, "bold"),
        fg_color=ACCENT, hover_color=ACCENT_HOV,
        text_color=PAPER,
        border_width=BORDER_W, border_color=BORDER,
        corner_radius=3, **kw
    )


def secondary_btn(parent, text: str, command=None, height: int = 44, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent, text=text, height=height, command=command,
        font=font(13),
        fg_color=PAPER, hover_color=BG_ALT,
        text_color=TEXT_MUTED,
        border_width=BORDER_W, border_color=BORDER,
        corner_radius=3, **kw
    )


def option_menu(parent, values: list, width: int = 0, **kw) -> ctk.CTkOptionMenu:
    """Styled dropdown that matches the warm-cream palette."""
    kwargs = dict(
        fg_color=PAPER, button_color=BG_DEEP, button_hover_color=BG_ALT,
        text_color=TEXT, dropdown_fg_color=PAPER,
        dropdown_hover_color=BG_ALT, dropdown_text_color=TEXT,
        corner_radius=3, font=font(13),
    )
    if width:
        kwargs["width"] = width
    kwargs.update(kw)
    return ctk.CTkOptionMenu(parent, values=values, **kwargs)


def scrollable(parent, **kw) -> ctk.CTkScrollableFrame:
    """Scrollable frame with themed scrollbar."""
    kwargs = dict(
        corner_radius=0, fg_color="transparent",
        scrollbar_button_color=BG_DEEP,
        scrollbar_button_hover_color=TEXT_GHOST,
    )
    kwargs.update(kw)
    return ctk.CTkScrollableFrame(parent, **kwargs)


def card_frame(parent, **kw) -> ctk.CTkFrame:
    """White card with dark 2px border."""
    return ctk.CTkFrame(parent, fg_color=PAPER, corner_radius=4,
                        border_width=BORDER_W, border_color=BORDER, **kw)


def attach_entry_menu(entry: ctk.CTkEntry) -> ctk.CTkEntry:
    """
    Добавляет к CTkEntry контекстное меню (ПКМ) и горячую клавишу Ctrl+A.
    Ctrl+C / Ctrl+V / Ctrl+X работают в tk.Entry по умолчанию.
    Привязывается напрямую к внутреннему tk.Entry (_entry), чтобы
    события мыши и клавиатуры не терялись через CTkEntry-обёртку.
    """
    inner: tk.Entry = entry._entry  # tk.Entry внутри CTkEntry (стабильно в CTk 5.x)

    def _select_all():
        inner.select_range(0, "end")
        inner.icursor("end")
        return "break"

    def _show_menu(event: tk.Event):
        menu = tk.Menu(
            inner, tearoff=0,
            bg=PAPER, fg=TEXT,
            activebackground=ACCENT_SOFT, activeforeground=TEXT,
            font=(_SANS, 12), bd=1, relief="solid",
        )
        menu.add_command(label="Вырезать",     accelerator="Ctrl+X",
                         command=lambda: inner.event_generate("<<Cut>>"))
        menu.add_command(label="Копировать",   accelerator="Ctrl+C",
                         command=lambda: inner.event_generate("<<Copy>>"))
        menu.add_command(label="Вставить",     accelerator="Ctrl+V",
                         command=lambda: inner.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Выделить всё", accelerator="Ctrl+A",
                         command=_select_all)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    inner.bind("<Button-3>", _show_menu)
    inner.bind("<Control-a>", lambda e: _select_all())
    inner.bind("<Control-A>", lambda e: _select_all())
    return entry


def styled_entry(parent, placeholder: str = "", show: str = "",
                 textvariable=None, **kw) -> ctk.CTkEntry:
    kwargs = dict(
        height=40, fg_color=PAPER,
        border_width=BORDER_W, border_color=BORDER,
        corner_radius=3, text_color=TEXT,
        placeholder_text=placeholder,
        placeholder_text_color=TEXT_GHOST,
        font=font(14),
    )
    if show:
        kwargs["show"] = show
    if textvariable is not None:
        kwargs["textvariable"] = textvariable
    kwargs.update(kw)
    entry = ctk.CTkEntry(parent, **kwargs)
    attach_entry_menu(entry)
    return entry
