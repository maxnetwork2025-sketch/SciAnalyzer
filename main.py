import ctypes
import traceback
from ui.login import LoginWindow
from ui.set_password_window import SetPasswordWindow
from ui.app import App
from db import init_db
from core.ollama_manager import ensure_running

# Говорим Windows что это отдельное приложение — иначе в панели задач
# отображается иконка Python, а не наша
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SciAnalyzer.App")


def _on_tk_error(exc, val, tb):
    """Подавляет безвредные ошибки customtkinter после уничтожения виджетов."""
    if "invalid command name" in str(val):
        return
    traceback.print_exception(exc, val, tb)


def main():
    init_db()
    ensure_running()

    login = LoginWindow()
    login.report_callback_exception = _on_tk_error
    login.mainloop()

    if not login.logged_in_user:
        return

    user = login.logged_in_user

    if user.get("needs_password"):
        spw = SetPasswordWindow(user["username"])
        spw.mainloop()
        if not spw.password_set:
            return  # закрыл окно не задав пароль — не пускаем
        user.pop("needs_password", None)

    app = App(current_user=user)
    app.report_callback_exception = _on_tk_error
    app.mainloop()


if __name__ == "__main__":
    main()
