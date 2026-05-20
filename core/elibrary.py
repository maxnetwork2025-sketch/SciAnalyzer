"""
Скраппер eLibrary.ru — работает через curl-cffi (имитация TLS-отпечатка Chrome).
Сайт блокирует стандартный Python SSL и требует авторизации для поиска.

Требования:
  - pip install curl-cffi
  - Логин и пароль личного кабинета elibrary.ru (бесплатная регистрация)

Хранение учётных данных: db.get_setting("elibrary_login") / "elibrary_password"

Поток:
  1. GET  https://elibrary.ru/                      → cookies SCookieGUID, SUserID
  2. POST https://elibrary.ru/start_session.asp      → авторизация, куки SID
  3. POST https://elibrary.ru/query_results.asp      → HTML-таблица результатов
  4. Парсинг: a[href^='item.asp'] → id, title, authors, year, journal
"""
from __future__ import annotations
import re
import time

from bs4 import BeautifulSoup

from core.api_client import Article

BASE_URL      = "https://elibrary.ru"
_LOGIN_URL    = f"{BASE_URL}/start_session.asp"
_SEARCH_URL   = f"{BASE_URL}/query_results.asp"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
}


def _make_session():
    from curl_cffi import requests as cf_requests
    s = cf_requests.Session(impersonate="chrome124")
    s.headers.update(_HEADERS)
    return s


class ElibraryScaper:
    """Поиск статей на elibrary.ru с авторизацией через личный кабинет."""

    def __init__(self):
        self._session = None
        self._authenticated = False
        self._auth_login: str = ""
        self._auth_pass:  str = ""

    def _get_credentials(self) -> tuple[str, str]:
        from db import get_setting
        return get_setting("elibrary_login"), get_setting("elibrary_password")

    def _ensure_session(self) -> bool:
        """Инициализирует сессию и выполняет авторизацию. Возвращает True при успехе."""
        login, password = self._get_credentials()
        if not login or not password:
            return False

        try:
            self._session = _make_session()
            self._session.get(BASE_URL, timeout=15)

            r = self._session.post(
                _LOGIN_URL,
                data={
                    "login":    login,
                    "password": password,
                    "rpage":    BASE_URL + "/",
                    "knowme":   "",
                },
                timeout=20,
            )
            # Success: redirected to main page; no "error" in URL
            if r.status_code == 200 and "error" not in r.url.lower():
                self._authenticated = True
                self._auth_login = login
                self._auth_pass  = password
                return True
        except Exception:
            pass
        self._authenticated = False
        return False

    def search(
        self,
        query:       str,
        max_results: int   = 20,
        depth:       int   = 1,
        delay:       float = 2.0,
        mode:        str   = "topic",
    ) -> list[Article]:
        # Перепроверяем учётные данные: если они изменились — переавторизуемся
        current_login, current_pass = self._get_credentials()
        needs_auth = (
            not self._authenticated
            or self._session is None
            or current_login != self._auth_login
            or current_pass  != self._auth_pass
        )
        if needs_auth:
            if not self._ensure_session():
                raise RuntimeError(
                    "eLibrary: не настроены учётные данные. "
                    "Укажите логин/пароль в Настройки → API-ключи."
                )

        page_size = 10
        results: list[Article] = []
        seen:    set[str]      = set()

        for page in range(depth):
            batch = self._fetch_page(query, page=page, page_size=page_size, mode=mode)
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

    def _fetch_page(
        self,
        query:     str,
        page:      int,
        page_size: int,
        mode:      str,
    ) -> list[Article]:
        if mode == "author":
            data = {
                "authors":      query,
                "where_author": "on",
                "type_article": "on",
                "search_morph": "on",
                "orderby":      "year",
                "order":        "rev",
                "start_page":   page + 1,
            }
        else:
            data = {
                "querybox":     query,
                "where_name":   "on",
                "where_abstract": "on",
                "type_article": "on",
                "search_morph": "on",
                "orderby":      "citings",
                "order":        "rev",
                "start_page":   page + 1,
            }

        try:
            r = self._session.post(_SEARCH_URL, data=data, timeout=25)
            r.raise_for_status()
        except Exception:
            return []

        return self._parse_results(r.text)

    def _parse_results(self, html: str) -> list[Article]:
        soup  = BeautifulSoup(html, "html.parser")
        items = soup.select("table#restab tr") or soup.select("tr.resrow")

        # If no known selector found, fall back to scanning all item.asp links
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

        # Authors: usually in next <font> or <span> sibling
        authors: list[str] = []
        author_tag = row.find("font", color=re.compile(r"gray|#[89aAbBcCdDeEfF]", re.I))
        if not author_tag:
            author_tag = row.find("i") or row.find("span", class_=re.compile(r"author", re.I))
        if author_tag:
            raw = author_tag.get_text(" ", strip=True)
            authors = [s.strip() for s in re.split(r"[,;]", raw) if s.strip()]

        # Year from text of the row
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
        """Fallback: collect all item.asp links as minimal Article objects."""
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
