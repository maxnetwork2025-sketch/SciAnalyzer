"""
Универсальный парсинг статьи по прямому URL.

Использование:
    scraper = ArticleScraper()
    article = scraper.scrape("https://arxiv.org/abs/1706.03762")
    # -> ScrapedArticle(title=..., content=..., authors=..., ...)

Стратегия:
    1. newspaper4k  — даёт title, text, authors, publish_date
    2. BeautifulSoup-фолбэк — если newspaper4k упал или ничего не распознал
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

import requests

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


@dataclass
class ScrapedArticle:
    url:          str
    title:        str             = ""
    content:      str             = ""
    source:       str             = ""
    language:     str             = ""
    published_at: datetime | None = None
    authors:      list[str]       = field(default_factory=list)


class ArticleScraper:
    """
    Универсальный парсер статей.
    Сначала пробует newspaper4k, при неудаче — BeautifulSoup-фолбэк.
    """

    def scrape(self, url: str) -> ScrapedArticle:
        try:
            result = self._scrape_newspaper4k(url)
            if result.title and result.content:
                return result
        except Exception:
            pass
        return self._scrape_bs4(url)

    def scrape_many(self, urls: list[str]) -> list[ScrapedArticle]:
        results = []
        for url in urls:
            try:
                results.append(self.scrape(url))
            except Exception:
                pass
        return results

    # ── Стратегия 1: newspaper4k ───────────────────────────────────────────

    def _scrape_newspaper4k(self, url: str) -> ScrapedArticle:
        from newspaper import Article as NpArticle  # type: ignore

        art = NpArticle(url, language="ru", request_timeout=20)
        art.download()
        art.parse()

        source = urlparse(url).netloc
        year   = ""
        if art.publish_date:
            year = str(art.publish_date.year)

        return ScrapedArticle(
            url=url,
            title=art.title or "",
            content=art.text or "",
            source=source,
            language=art.meta_lang or "",
            published_at=art.publish_date,
            authors=list(art.authors),
        )

    # ── Стратегия 2: BeautifulSoup fallback ───────────────────────────────

    def _scrape_bs4(self, url: str) -> ScrapedArticle:
        from bs4 import BeautifulSoup  # type: ignore

        r = _SESSION.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")

        # пробуем взять заголовок
        title = ""
        if (h1 := soup.find("h1")):
            title = h1.get_text(strip=True)
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

        # предпочитаем <article> если есть, иначе собираем все <p>
        content_parts: list[str] = []
        article_tag = soup.find("article")
        if article_tag:
            for p in article_tag.find_all("p"):
                t = p.get_text(" ", strip=True)
                if t:
                    content_parts.append(t)
        else:
            for p in soup.find_all("p"):
                t = p.get_text(" ", strip=True)
                if len(t) > 40:
                    content_parts.append(t)

        content = "\n".join(content_parts)[:15_000]
        source  = urlparse(url).netloc

        return ScrapedArticle(
            url=url,
            title=title or url,
            content=content,
            source=source,
        )
