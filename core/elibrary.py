"""
Скраппер eLibrary.ru — работает через curl-cffi (имитация TLS-отпечатка Chrome).

Поток:
  1. GET  https://www.elibrary.ru/            → cookies SCookieGUID, SUserID
  2. POST /start_session.asp                  → авторизация
  3. GET  /querybox.asp                       → форма поиска со всеми hidden-полями
  4. POST /querybox.asp   ftext=<запрос>      → HTML с результатами / redirect на query_results.asp
  5. Парсинг: a[href*='item.asp'] → title, authors, year
"""
from __future__ import annotations
import re
import time

from bs4 import BeautifulSoup

from core.api_client import Article

BASE_URL      = "https://www.elibrary.ru"
_LOGIN_URL    = f"{BASE_URL}/start_session.asp"
_QUERYBOX_URL = f"{BASE_URL}/querybox.asp"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
}


def _make_session():
    from curl_cffi import requests as cf_requests
    for target in ("chrome131", "chrome124", "chrome110"):
        try:
            s = cf_requests.Session(impersonate=target)
            s.headers.update(_HEADERS)
            return s
        except Exception:
            continue
    raise RuntimeError("curl_cffi: ни один профиль Chrome не поддерживается")


def _is_captcha(html: str) -> bool:
    return "page_captcha" in html or "captcha" in html.lower()


class ElibraryScaper:
    """Поиск статей на elibrary.ru с авторизацией через личный кабинет."""

    def __init__(self, user_id: int = 0):
        self._user_id = user_id
        self._session = None
        self._authenticated = False
        self._auth_login: str = ""
        self._auth_pass:  str = ""

    def _get_credentials(self) -> tuple[str, str]:
        from db import get_user_setting, get_setting, save_user_setting
        login    = get_user_setting(self._user_id, "elibrary_login")
        password = get_user_setting(self._user_id, "elibrary_password")
        # Миграция: старый глобальный формат
        if not login:
            login    = get_setting("elibrary_login")
            password = get_setting("elibrary_password")
            if login and self._user_id:
                save_user_setting(self._user_id, "elibrary_login",    login)
                save_user_setting(self._user_id, "elibrary_password", password)
        return login, password

    def _ensure_session(self) -> None:
        """Инициализирует сессию и выполняет авторизацию. Бросает RuntimeError при неудаче."""
        login, password = self._get_credentials()
        if not login or not password:
            raise RuntimeError("нажмите «Войти в eLib» и введите логин/пароль")

        try:
            self._session = _make_session()
        except ImportError:
            raise RuntimeError("не установлен пакет curl-cffi (pip install curl-cffi)")

        try:
            self._session.headers["Referer"] = BASE_URL + "/"
            self._session.get(BASE_URL, timeout=60)
            time.sleep(1)
            r = self._session.post(
                _LOGIN_URL,
                data={
                    "login":    login,
                    "password": password,
                    "rpage":    BASE_URL + "/",
                    "knowme":   "",
                },
                timeout=1120,
            )
        except Exception as e:
            self._authenticated = False
            msg = str(e)
            if "28" in msg or "timed out" in msg.lower():
                raise RuntimeError(
                    "elibrary.ru не отвечает (таймаут). "
                    "Проверьте, открывается ли сайт в браузере."
                ) from e
            raise RuntimeError(f"ошибка соединения: {e}") from e

        if _is_captcha(r.text):
            self._authenticated = False
            raise RuntimeError(
                "elibrary.ru просит капчу — подождите 15–30 минут и попробуйте снова"
            )

        if "error" in r.url.lower():
            self._authenticated = False
            raise RuntimeError("неверный логин или пароль eLibrary")

        self._authenticated = True
        self._auth_login = login
        self._auth_pass  = password

    def search(
        self,
        query:       str,
        max_results: int   = 20,
        depth:       int   = 1,
        delay:       float = 3.0,
        mode:        str   = "topic",
    ) -> list[Article]:
        current_login, current_pass = self._get_credentials()
        needs_auth = (
            not self._authenticated
            or self._session is None
            or current_login != self._auth_login
            or current_pass  != self._auth_pass
        )
        if needs_auth:
            self._ensure_session()

        results: list[Article] = []
        seen:    set[str]      = set()

        for page in range(depth):
            batch = self._fetch_page(query, page=page, mode=mode)
            for art in batch:
                key = art.url or art.title
                if key not in seen:
                    seen.add(key)
                    results.append(art)
            if not batch or len(results) >= max_results:
                break
            if page < depth - 1:
                time.sleep(delay)

        return results[:max_results]

    def _fetch_page(self, query: str, page: int, mode: str) -> list[Article]:
        try:
            # Шаг 1: GET форму — захватываем все поля включая hidden
            self._session.headers["Referer"] = BASE_URL + "/defaultx.asp"
            r_form = self._session.get(_QUERYBOX_URL, timeout=60)

            if _is_captcha(r_form.text):
                raise RuntimeError(
                    "elibrary.ru просит капчу — подождите 15–30 минут и попробуйте снова"
                )

            soup_form = BeautifulSoup(r_form.text, "html.parser")
            form = soup_form.find("form", action=re.compile(r"querybox", re.I))

            # Собираем все поля формы с дефолтными значениями
            data: dict = {}
            if form:
                for inp in form.find_all(["input", "textarea", "select"]):
                    name = inp.get("name")
                    if name:
                        data[name] = inp.get("value", "")

            # Перекрываем своими параметрами
            if mode == "author":
                data.update({
                    "ftext":        "",
                    "authors_all":  query,
                    "type_article": "on",
                    "search_morph": "on",
                    "orderby":      "year",
                    "order":        "rev",
                    "changed":      "1",
                    "start_page":   str(page + 1),
                })
            else:
                data.update({
                    "ftext":          query,
                    "where_name":     "on",
                    "where_abstract": "on",
                    "type_article":   "on",
                    "search_morph":   "on",
                    "orderby":        "rank",
                    "order":          "rev",
                    "changed":        "1",
                    "start_page":     str(page + 1),
                })

            # Шаг 2: POST поиска
            self._session.headers["Referer"] = _QUERYBOX_URL
            time.sleep(1)
            r = self._session.post(_QUERYBOX_URL, data=data, timeout=60)
            r.raise_for_status()

            if _is_captcha(r.text):
                raise RuntimeError(
                    "elibrary.ru просит капчу — подождите 15–30 минут и попробуйте снова"
                )

        except RuntimeError:
            raise
        except Exception:
            return []

        return self._parse_results(r.text)

    def _parse_results(self, html: str) -> list[Article]:
        soup  = BeautifulSoup(html, "html.parser")
        items = soup.select("table#restab tr") or soup.select("tr.resrow")

        if not items:
            return self._parse_fallback(soup)

        articles: list[Article] = []
        for row in items:
            art = self._parse_row(row)
            if art:
                articles.append(art)
        return articles

    def _parse_row(self, row) -> Article | None:
        link = row.find("a", href=re.compile(r"item\.asp"))
        if not link:
            return None

        title = link.get_text(strip=True)
        href  = link.get("href", "")
        url   = href if href.startswith("http") else f"{BASE_URL}/{href.lstrip('/')}"

        authors: list[str] = []
        author_tag = row.find("font", color=re.compile(r"gray|#[89aAbBcCdDeEfF]", re.I))
        if not author_tag:
            author_tag = row.find("i") or row.find("span", class_=re.compile(r"author", re.I))
        if author_tag:
            raw = author_tag.get_text(" ", strip=True)
            authors = [s.strip() for s in re.split(r"[,;]", raw) if s.strip()]

        year = ""
        m = re.search(r"\b(19|20)\d{2}\b", row.get_text())
        if m:
            year = m.group(0)

        return Article(
            title=title,
            authors=authors,
            url=url,
            year=year,
            source="eLibrary",
            abstract="",
        )

    def _parse_fallback(self, soup: BeautifulSoup) -> list[Article]:
        articles: list[Article] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=re.compile(r"item\.asp")):
            href = a.get("href", "")
            url  = href if href.startswith("http") else f"{BASE_URL}/{href.lstrip('/')}"
            if url in seen:
                continue
            seen.add(url)
            title = a.get_text(strip=True)
            if not title:
                continue
            year = ""
            m = re.search(r"\b(20\d{2})\b", url)
            if m:
                year = m.group(1)
            articles.append(Article(
                title=title, authors=[], url=url,
                year=year, source="eLibrary", abstract="",
            ))
        return articles

    def reset_auth(self) -> None:
        """Сбрасывает сессию — используется при смене учётных данных."""
        self._session = None
        self._authenticated = False
