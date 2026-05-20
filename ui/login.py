import customtkinter as ctk
from core.paths import bundled
from db import authenticate_user
from ui.theme import (
    BG, PAPER, TEXT, TEXT_MUTED, TEXT_GHOST,
    BORDER, BORDER_W, ACCENT, ACCENT_SOFT, DANGER,
    font, styled_entry, card_frame, primary_btn,
)


class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.title("SciAnalyzer — Вход")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.iconbitmap(str(bundled("paigeForStatusBar.ico")))

        self.logged_in_user = None
        self._build()

        # centre on screen after widgets are measured
        self.update_idletasks()
        w, h = 440, 440
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        self.bind("<Return>", lambda _: self._on_login())

    # ──────────────────────────────────────────────────────────────────────────

    def _build(self):
        # Grid: row 0 (top flex) / row 1 (content) / row 2 (bottom flex)
        # Rows 0 & 2 have equal weight → content is perfectly centred
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=1, column=0, sticky="ew", padx=40)

        # ── Logo "NA" ──────────────────────────────────────────────────────
        logo_box = ctk.CTkFrame(center, width=64, height=64,
                                corner_radius=8, fg_color=ACCENT)
        logo_box.pack()
        logo_box.pack_propagate(False)
        ctk.CTkLabel(logo_box, text="NA",
                     font=font(26, "bold"), text_color=PAPER).pack(expand=True)

        # ── Headlines ─────────────────────────────────────────────────────
        ctk.CTkLabel(center, text="Добро пожаловать",
                     font=font(24, "bold"), text_color=TEXT).pack(pady=(12, 4))
        ctk.CTkLabel(center, text="Войдите в систему анализа статей",
                     font=font(13), text_color=TEXT_MUTED).pack(pady=(0, 14))

        # ── Form card ─────────────────────────────────────────────────────
        card = card_frame(center)
        card.pack(fill="x")

        ctk.CTkLabel(card, text="ЛОГИН",
                     font=font(10, "bold"), text_color=TEXT_GHOST,
                     anchor="w").pack(anchor="w", padx=20, pady=(16, 3))
        self.user_entry = styled_entry(card, placeholder="admin")
        self.user_entry.pack(padx=20, fill="x")

        ctk.CTkLabel(card, text="ПАРОЛЬ",
                     font=font(10, "bold"), text_color=TEXT_GHOST,
                     anchor="w").pack(anchor="w", padx=20, pady=(10, 3))
        self.pass_entry = styled_entry(card, placeholder="••••••••", show="•")
        self.pass_entry.pack(padx=20, fill="x")

        # ── Error label ───────────────────────────────────────────────────
        self.error_label = ctk.CTkLabel(card, text="",
                                        text_color=DANGER, font=font(12))
        self.error_label.pack(pady=(2, 2))

        # ── Login button ──────────────────────────────────────────────────
        primary_btn(card, "Войти →",
                    command=self._on_login).pack(padx=20, fill="x", pady=(2, 16))


    # ──────────────────────────────────────────────────────────────────────────

    def _on_login(self):
        username = self.user_entry.get().strip()
        password = self.pass_entry.get()

        if not username:
            self.error_label.configure(text="Введите имя пользователя")
            return

        user = authenticate_user(username, password)
        if user:
            self.logged_in_user = user
            self.destroy()
        else:
            self.error_label.configure(text="Неверный логин или пароль")
            self.pass_entry.delete(0, "end")
            self.pass_entry.focus()

    def _on_register(self):
        self.error_label.configure(
            text="Регистрация будет доступна позже", text_color="#4a5a90")
