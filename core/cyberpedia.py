"""
Скраппер CyberPedia.su — работает через Яндекс.Поиск по сайту.
Searchid 2392445 зарегистрирован на cyberpedia.su; Яндекс возвращает
title + сниппет + URL без необходимости обращаться к самому сайту.

URL поиска: GET https://yandex.ru/search/site/
            ?searchid=2392445&text=...&l10n=ru&p=N
Пагинация: параметр p (0-based), по 10 результатов на страницу.
"""
from __future__ import annotations
import re
import time

import requests
from bs4 import BeautifulSoup

from core.api_client import Article

_YANDEX_SEARCH = "https://yandex.ru/search/site/"
_SEARCH_ID      = "2392445"
_BASE_URL       = "https://cyberpedia.su"

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
    "Referer":         "https://cyberpedia.su/",
})


class CyberpediaScraper:
    """Поиск по cyberpedia.su через Яндекс.Поиск по сайту."""

    def search(
        self,
        query:       str,
        max_results: int   = 20,
        depth:       int   = 1,
        delay:       float = 2.0,
        mode:        str   = "topic",
    ) -> list[Article]:
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
        try:
            r = _SESSION.get(
                _YANDEX_SEARCH,
                params={
                    "searchid": _SEARCH_ID,
                    "text":     query,
                    "l10n":     "ru",
                    "p":        page,
                },
                timeout=20,
            )
            r.raise_for_status()
        except Exception:
            return []

        soup    = BeautifulSoup(r.text, "html.parser")
        articles: list[Article] = []

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not (href.startswith(_BASE_URL) and href != _BASE_URL + "/"):
                continue

            title = a.get_text(strip=True)
            if not title:
                continue

            # идём вверх по DOM чтобы найти блок со сниппетом вокруг ссылки
            block = a
            for _ in range(5):
                parent = block.find_parent(["div", "li", "article", "p"])
                if not parent:
                    break
                block_text = parent.get_text(" ", strip=True)
                if len(block_text) > len(title) + 10:
                    block = parent
                    break
                block = parent

            snippet = block.get_text(" ", strip=True)
            # убираем нумерацию ("1. ") и дублирующийся заголовок
            snippet = re.sub(r"^\d+\.\s*", "", snippet)
            snippet = snippet.replace(title, "").strip()

            articles.append(Article(
                title=title,
                authors=[],
                url=href,
                year="",
                source="CyberPedia",
                abstract=snippet,
            ))

        return articles
