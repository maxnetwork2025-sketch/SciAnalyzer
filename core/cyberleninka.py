"""
Скраппер CyberLeninka.ru — работает полностью в фоне без браузера.
Использует внутренний JSON-API сайта (тот же, что использует фронтенд):
  POST /api/search  {"q": ..., "size": ..., "from": ..., "mode": "articles"}

Возвращает те же объекты Article, что и SciAPIClient, поэтому карточки,
кнопки скачивания и перевода работают без изменений.
"""
from __future__ import annotations
import re
import time

import requests
from bs4 import BeautifulSoup

from core.api_client import Article

BASE_URL    = "https://cyberleninka.ru"
_API_SEARCH = f"{BASE_URL}/api/search"

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/html, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
    "Referer":         "https://cyberleninka.ru/",
    "Content-Type":    "application/json",
})

_RE_TAGS = re.compile(r"<[^>]+>")


def _strip_tags(text: str) -> str:
    return _RE_TAGS.sub("", text).strip()


class CyberLeninkaScraper:
    """
    Поиск статей на CyberLeninka.ru.

    Стратегия:
      1. POST /api/search {"q":..., "size":..., "from":..., "mode":"articles"} → JSON
      2. GET  /search?q=...  → HTML+bs4 (резервный путь)
    """

    def search(
        self,
        query:       str,
        max_results: int   = 20,
        depth:       int   = 1,
        delay:       float = 2.0,
        mode:        str   = "topic",   # "topic" | "author"
    ) -> list[Article]:
        # При поиске по автору ограничиваем запрос кавычками для точного совпадения
        effective_query = f'"{query}"' if mode == "author" else query

        page_size = 10
        results:  list[Article] = []
        seen:     set[str]      = set()

        for page in range(depth):
            batch = self._fetch_page(effective_query,
                                     offset=page * page_size,
                                     size=page_size)
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

    # ── API (primary) ─────────────────────────────────────────────────────────

    def _fetch_page(self, query: str, offset: int, size: int) -> list[Article]:
        try:
            r = _SESSION.post(
                _API_SEARCH,
                json={"q": query, "size": size, "from": offset, "mode": "articles"},
                timeout=20,
            )
            r.raise_for_status()
            data  = r.json()
            items = data.get("articles") or []
            if items:
                return [self._parse_api(a) for a in items]
        except Exception:
            pass

        return self._fetch_html(query, page=offset // max(size, 1))

    def _parse_api(self, item: dict) -> Article:
        # title — may contain <b> highlight tags
        title = _strip_tags(item.get("name") or "")

        # abstract — may contain <b> highlight tags
        abstract = _strip_tags(item.get("annotation") or "")

        year = str(item.get("year") or "")

        # URL: field "link" is a relative path like /article/n/slug
        link = item.get("link") or ""
        url  = f"{BASE_URL}{link}" if link.startswith("/") else link

        # authors: list of plain strings
        raw_authors = item.get("authors") or []
        if isinstance(raw_authors, list):
            authors = [str(a).strip() for a in raw_authors if a]
        else:
            authors = [str(raw_authors).strip()]

        # journal: plain string
        journal = str(item.get("journal") or "").strip()

        return Article(
            title=title,
            authors=authors,
            url=url,
            year=year,
            source="CyberLeninka",
            abstract=abstract,
        )

    # ── HTML fallback ─────────────────────────────────────────────────────────

    def _fetch_html(self, query: str, page: int = 0) -> list[Article]:
        try:
            r = _SESSION.get(
                f"{BASE_URL}/search",
                params={"q": query, "page": page},
                timeout=20,
            )
            r.raise_for_status()
        except Exception:
            return []

        soup  = BeautifulSoup(r.text, "html.parser")
        cards = (
            soup.select("ul#search-result li.item")
            or soup.select("li.item")
            or soup.select("article.item")
            or soup.select(".search-result-item")
        )

        articles: list[Article] = []
        for card in cards:
            try:
                art = self._parse_card(card)
                if art:
                    articles.append(art)
            except Exception:
                continue
        return articles

    def _parse_card(self, card) -> Article | None:
        link = None
        h2 = card.find("h2")
        if h2:
            link = h2.find("a", href=True)
        if not link:
            link = card.find("a", href=re.compile(r"/article/"))
        if not link:
            return None

        title = link.get_text(strip=True)
        href  = link.get("href", "")
        url   = f"{BASE_URL}{href}" if href.startswith("/") else href

        authors: list[str] = []
        for sel in [".author", ".authors", "i.author"]:
            tag = card.select_one(sel)
            if tag:
                text = tag.get_text(strip=True)
                authors = [s.strip() for s in re.split(r"[,;]", text) if s.strip()]
                break

        year  = ""
        match = re.search(r"\b(19|20)\d{2}\b", card.get_text())
        if match:
            year = match.group(0)

        abstract = ""
        for sel in [".abstract", ".anons", "p"]:
            tag = card.select_one(sel)
            if tag:
                abstract = tag.get_text(strip=True)
                break

        return Article(title=title, authors=authors, url=url,
                       year=year, source="CyberLeninka", abstract=abstract)
