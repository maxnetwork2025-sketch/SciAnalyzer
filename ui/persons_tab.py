import customtkinter as ctk
from ui.theme import BG


class PersonsTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=BG)
