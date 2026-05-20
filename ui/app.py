import customtkinter as ctk
from core.paths import bundled

from ui.search_tab    import SearchTab
from ui.results_tab   import LibraryTab
from ui.documents_tab import DocumentsTab
from ui.compare_tab   import CompareTab
from ui.settings_tab  import SettingsTab

from ui.theme import (
    BG, BG_ALT, BG_DEEP, PAPER, TEXT, TEXT_MUTED,
    BORDER, BORDER_SOFT, ACCENT, ACCENT_SOFT,
    font, secondary_btn,
)


class App(ctk.CTk):
    def __init__(self, current_user: dict):
        super().__init__()
        self.current_user = current_user
        self._frames:          dict = {}
        self._nav_btns:        dict = {}
        self._nav_indicators:  dict = {}

        self.title("SciAnalyzer")
        self.geometry("1280x800")
        self.minsize(1024, 700)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=BG)
        self.iconbitmap(str(bundled("paigeForStatusBar.ico")))

        self._build_topbar()
        self._build_nav()
        self._build_content()

    # ──────────────────────────────────────────────────────────────────────────
    #  Топбар
    # ──────────────────────────────────────────────────────────────────────────

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, height=46, corner_radius=0, fg_color=BG)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # bottom separator
        ctk.CTkFrame(self, height=2, corner_radius=0,
                     fg_color=BORDER_SOFT).pack(fill="x")

        # ── Left: logo square + app name ──────────────────────────────────
        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", padx=20, fill="y")

        logo = ctk.CTkFrame(left, width=28, height=28,
                            corner_radius=4, fg_color=ACCENT)
        logo.pack(side="left", pady=9)
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="NA", font=font(11, "bold"),
                     text_color=PAPER).pack(expand=True)

        ctk.CTkLabel(left, text="SciAnalyzer",
                     font=font(16, "bold"), text_color=TEXT).pack(
                         side="left", padx=(10, 0))

        # ── Right: avatar · username · role chip · logout ─────────────────
        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.pack(side="right", padx=20, fill="y")

        # "Выйти →" button
        secondary_btn(right, "Выйти →", command=self._logout,
                      height=30).pack(side="right", pady=8)

        # Role chip
        is_admin = bool(self.current_user.get("is_admin"))
        role_chip = ctk.CTkFrame(
            right,
            fg_color=ACCENT if is_admin else BG_DEEP,
            corner_radius=3,
        )
        role_chip.pack(side="right", padx=(0, 8), pady=14)
        ctk.CTkLabel(
            role_chip,
            text="админ" if is_admin else "польз.",
            font=font(11, "bold"),
            text_color=PAPER if is_admin else TEXT_MUTED,
        ).pack(padx=8, pady=2)

        # Username
        ctk.CTkLabel(right,
                     text=self.current_user["username"],
                     font=font(13), text_color=TEXT_MUTED).pack(
                         side="right", padx=(0, 6))

        # Avatar circle (initials)
        initial = self.current_user["username"][0].upper()
        avatar = ctk.CTkFrame(right, width=32, height=32,
                              corner_radius=16, fg_color=ACCENT_SOFT)
        avatar.pack(side="right", padx=(0, 6), pady=7)
        avatar.pack_propagate(False)
        ctk.CTkLabel(avatar, text=initial, font=font(12, "bold"),
                     text_color=ACCENT).pack(expand=True)

    # ──────────────────────────────────────────────────────────────────────────
    #  Таб-бар
    # ──────────────────────────────────────────────────────────────────────────

    def _build_nav(self):
        # Outer container: BG_ALT strip (the tab bar)
        nav = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color=BG_ALT)
        nav.pack(fill="x")
        nav.pack_propagate(False)

        # 2 px dark line below tabs
        ctk.CTkFrame(self, height=2, corner_radius=0,
                     fg_color=BORDER).pack(fill="x")

        tabs = [
            ("Поиск",      "search"),
            ("Библиотека", "results"),
            ("Создание файлов по шаблону", "authors"),
            ("Сравнение",  "compare"),
        ]
        if self.current_user.get("is_admin"):
            tabs.append(("Настройки", "settings"))

        for label, key in tabs:
            # Each tab is a column: [button 37px] + [indicator strip 3px]
            col = ctk.CTkFrame(nav, fg_color="transparent", corner_radius=0)
            col.pack(side="left", fill="both", expand=True)

            btn = ctk.CTkButton(
                col,
                text=label,
                height=37,
                corner_radius=0,
                font=font(13),
                fg_color="transparent",
                text_color=TEXT_MUTED,
                hover_color=BG_DEEP,
                border_width=0,
                command=lambda k=key: self._switch(k),
            )
            btn.pack(fill="both", expand=True)

            # Accent underline — 3 px at the very bottom of each tab
            indicator = ctk.CTkFrame(col, height=3, corner_radius=0,
                                     fg_color="transparent")
            indicator.pack(fill="x")

            self._nav_btns[key]       = btn
            self._nav_indicators[key] = indicator

    # ──────────────────────────────────────────────────────────────────────────
    #  Область контента
    # ──────────────────────────────────────────────────────────────────────────

    def _build_content(self):
        self._content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG)
        self._content.pack(fill="both", expand=True)
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        self._tab_classes: dict = {
            "search":  SearchTab,
            "results": LibraryTab,
            "authors": DocumentsTab,
            "compare": CompareTab,
        }
        if self.current_user.get("is_admin"):
            self._tab_classes["settings"] = SettingsTab

        self._switch("search")

    # ──────────────────────────────────────────────────────────────────────────
    #  Переключение вкладок
    # ──────────────────────────────────────────────────────────────────────────

    def _switch(self, key: str):
        if key not in self._frames:
            cls = self._tab_classes[key]
            frame = (cls(self._content, self.current_user)
                     if cls in (SettingsTab, SearchTab, LibraryTab, DocumentsTab, CompareTab)
                     else cls(self._content))
            frame.grid(row=0, column=0, sticky="nsew")
            self._frames[key] = frame

        self._frames[key].tkraise()

        for k, btn in self._nav_btns.items():
            active = (k == key)
            btn.configure(
                fg_color=PAPER     if active else "transparent",
                text_color=TEXT    if active else TEXT_MUTED,
                font=font(13, "bold" if active else "normal"),
            )
            self._nav_indicators[k].configure(
                fg_color=ACCENT if active else "transparent"
            )

    def _logout(self):
        self.destroy()
