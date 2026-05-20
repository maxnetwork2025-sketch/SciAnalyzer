"""
Скраппер moluch.ru («Молодой учёный») — работает в фоне без браузера.

Стратегия: журнал использует Next.js (поиск клиентский, API закрыт),
однако страницы выпусков /archive/NNN/ полностью рендерятся на сервере
и содержат все ссылки вида /archive/NNN/MMMMM с заголовками статей.

Алгоритм:
  1. Получить список последних N выпусков с /archive/  (SSR-страница)
  2. Для каждого выпуска загрузить страницу выпуска, собрать ссылки+заголовки
  3. Отфильтровать по ключевому слову в заголовке (case-insensitive)
  4. Для найденных статей загрузить страницу статьи → авторы + аннотация
  5. Вернуть результаты

depth=1 → 5 последних выпусков, depth=3 → 15, depth=10 → 40.
"""
from __future__ import annotations
import re
import time

import requests
from bs4 import BeautifulSoup

from core.api_client import Article

BASE_URL     = "https://moluch.ru"
_ARCHIVE_URL = f"{BASE_URL}/archive/"

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
    "Referer":         "https://moluch.ru/",
})

_ISSUES_PER_DEPTH = 5   # multiplied by depth value


class MoluchScraper:
    """Поиск статей на moluch.ru по обходу последних выпусков архива."""

    def search(
        self,
        query:       str,
        max_results: int   = 20,
        depth:       int   = 1,
        delay:       float = 2.0,
        mode:        str   = "topic",
    ) -> list[Article]:
        num_issues = depth * _ISSUES_PER_DEPTH
        issues     = self._get_recent_issues(num_issues)

        results: list[Article] = []
        seen:    set[str]      = set()
        query_lc = query.lower()

        for i, issue_path in enumerate(issues):
            if len(results) >= max_results:
                break

            candidates = self._search_issue(issue_path, query_lc, mode)
            for title, url in candidates:
                if url in seen:
                    continue
                seen.add(url)

                art = self._fetch_article(url, title)
                if art:
                    results.append(art)
                if len(results) >= max_results:
                    break

            if i < len(issues) - 1 and len(results) < max_results:
                time.sleep(delay)

        return results[:max_results]

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _get_recent_issues(self, n: int) -> list[str]:
        """Return up to n unique /archive/NNN/ paths, most recent first."""
        try:
            r = _SESSION.get(_ARCHIVE_URL, timeout=20)
            r.raise_for_status()
        except Exception:
            return []

        soup = BeautifulSoup(r.content, "html.parser")
        seen: set[str] = set()
        issues: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.match(r"^/archive/\d+/$", href) and href not in seen:
                seen.add(href)
                issues.append(href)
                if len(issues) >= n:
                    break
        return issues

    def _search_issue(
        self,
        issue_path: str,
        query_lc:   str,
        mode:       str,
    ) -> list[tuple[str, str]]:
        """Return (title, full_url) pairs from issue page matching query."""
        try:
            r = _SESSION.get(BASE_URL + issue_path, timeout=20)
            r.raise_for_status()
        except Exception:
            return []

        soup    = BeautifulSoup(r.content, "html.parser")
        matches: list[tuple[str, str]] = []
        seen:    set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not re.match(r"^/archive/\d+/\d+$", href):
                continue
            if href in seen:
                continue
            seen.add(href)

            title = a.get_text(strip=True)
            if not title:
                continue

            needle = title.lower()
            if mode == "author":
                # Author search: keyword appears in text around the link
                parent_text = ""
                p = a.find_parent()
                if p:
                    parent_text = p.get_text(" ", strip=True).lower()
                if query_lc not in needle and query_lc not in parent_text:
                    continue
            else:
                if query_lc not in needle:
                    continue

            matches.append((title, BASE_URL + href))

        return matches

    def _fetch_article(self, url: str, fallback_title: str) -> Article | None:
        """Load article page to get authors, abstract, year."""
        try:
            r = _SESSION.get(url, timeout=20)
            r.raise_for_status()
        except Exception:
            # Return minimal article using data already known from issue listing
            return Article(
                title=fallback_title,
                authors=[],
                url=url,
                year="",
                source="МолодойУчёный",
                abstract="",
            )

        soup = BeautifulSoup(r.content, "html.parser")

        # Title from h1 (more complete than link text in issue listing)
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else fallback_title

        # Authors
        authors = [
            tag.get_text(strip=True)
            for tag in soup.select("[itemprop=author]")
            if tag.get_text(strip=True)
        ]

        # Abstract from meta description
        meta = soup.find("meta", {"name": "description"})
        abstract = meta.get("content", "").strip() if meta else ""

        # Year from article:published_time meta
        year = ""
        pub_time = soup.find("meta", {"property": "article:published_time"})
        if pub_time:
            m = re.search(r"(20\d{2})", pub_time.get("content", ""))
            if m:
                year = m.group(1)

        return Article(
            title=title,
            authors=authors,
            url=url,
            year=year,
            source="МолодойУчёный",
            abstract=abstract,
        )
