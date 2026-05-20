"""
Скраппер sibac.info — работает полностью в фоне без браузера.
Использует Drupal-поиск: GET /search/node?keys=...&page=N
Результаты: ol.search-results li  →  h3.title a (заголовок + URL)
                                  →  .search-snippet (аннотация)

allow_redirects=False обязателен: без него сайт уходит в бесконечный
редиректный цикл при некоторых запросах.
"""
from __future__ import annotations
import re
import time

import requests
from bs4 import BeautifulSoup

from core.api_client import Article

BASE_URL    = "https://sibac.info"
_SEARCH_URL = f"{BASE_URL}/search/node"

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
    "Referer":         "https://sibac.info/",
})

_SESSION_INITIALIZED = False


def _init_session() -> None:
    """Lazy: получаем cookie entrypage при первом реальном запросе."""
    global _SESSION_INITIALIZED
    if not _SESSION_INITIALIZED:
        try:
            _SESSION.get(BASE_URL, timeout=10, allow_redirects=False)
            _SESSION_INITIALIZED = True
        except Exception:
            pass


class SibacScraper:
    """Поиск статей на sibac.info через Drupal-поиск (/search/node)."""

    def search(
        self,
        query:       str,
        max_results: int   = 20,
        depth:       int   = 1,
        delay:       float = 2.0,
        mode:        str   = "topic",   # "topic" | "author"
    ) -> list[Article]:
        # Drupal-поиск ищет по всем полям; кавычки дают точное совпадение имени автора
        effective_query = f'"{query}"' if mode == "author" else query

        results: list[Article] = []
        seen:    set[str]      = set()

        for page in range(depth):
            batch = self._fetch_page(effective_query, page=page)
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

    def _fetch_page(self, query: str, page: int = 0) -> list[Article]:
        _init_session()
        try:
            r = _SESSION.get(
                _SEARCH_URL,
                params={"keys": query, "page": page},
                timeout=20,
                allow_redirects=False,
            )
            r.raise_for_status()
        except Exception:
            return []

        soup  = BeautifulSoup(r.text, "html.parser")
        items = soup.select("ol.search-results li")

        articles: list[Article] = []
        for item in items:
            try:
                art = self._parse_item(item)
                if art:
                    articles.append(art)
            except Exception:
                continue
        return articles

    def _parse_item(self, item) -> Article | None:
        link = item.select_one("h3.title a") or item.select_one("h3 a")
        if not link:
            return None

        title = link.get_text(strip=True)
        href  = link.get("href", "")
        url   = href if href.startswith("http") else f"{BASE_URL}{href}"

        snippet = ""
        snip_tag = item.select_one(".search-snippet")
        if snip_tag:
            snippet = snip_tag.get_text(" ", strip=True)

        # Год из сниппета, если присутствует
        year  = ""
        m = re.search(r"\b(19|20)\d{2}\b", snippet)
        if m:
            year = m.group(0)

        return Article(
            title=title,
            authors=[],
            url=url,
            year=year,
            source="SibAC",
            abstract=snippet,
        )
