"""
Поиск научных статей через три бесплатных публичных API:
  arXiv, PubMed (NCBI E-utilities), Semantic Scholar.

Использование:
    client = SciAPIClient()
    articles = client.search("transformer attention", mode="topic", max_per_source=10)
    articles = client.search("Vaswani A",            mode="author", max_per_source=10)
"""
from __future__ import annotations
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import requests

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "SciAnalyzer/1.0"


@dataclass
class Article:
    title:    str
    authors:  list[str]
    url:      str
    year:     str
    source:   str
    abstract: str = ""


SOURCES = ("arxiv", "pubmed", "semantic_scholar")

SOURCE_LABELS = {
    "arxiv":            "arXiv",
    "pubmed":           "PubMed",
    "semantic_scholar": "Semantic Scholar",
}


class SciAPIClient:
    """Единый клиент для поиска научных статей."""

    def search(
        self,
        query:          str,
        mode:           str       = "topic",   # "topic" | "author"
        sources:        list[str] | None = None,
        max_per_source: int       = 10,
    ) -> list[Article]:
        """Ищет статьи во всех указанных источниках. Ошибки отдельных источников игнорируются."""
        active = [s for s in (sources or SOURCES) if s in SOURCES]
        results: list[Article] = []

        for src in active:
            try:
                results.extend(self.search_source(src, query, mode, max_per_source))
            except Exception:
                pass

        return results

    def search_source(
        self,
        source:         str,
        query:          str,
        mode:           str = "topic",
        max_per_source: int = 10,
    ) -> list[Article]:
        """Поиск в одном источнике. Бросает исключение при сетевой ошибке."""
        fn = self._dispatch(source, mode)
        return fn(query, max_per_source)

    # ── Диспетчер ──────────────────────────────────────────────────────────

    def _dispatch(self, source: str, mode: str):
        table = {
            ("arxiv",            "topic"):  self._arxiv_topic,
            ("arxiv",            "author"): self._arxiv_author,
            ("pubmed",           "topic"):  self._pubmed_topic,
            ("pubmed",           "author"): self._pubmed_author,
            ("semantic_scholar", "topic"):  self._ss_topic,
            ("semantic_scholar", "author"): self._ss_author,
        }
        return table.get((source, mode), table[(source, "topic")])

    # ── arXiv ──────────────────────────────────────────────────────────────

    def _arxiv_topic(self, query: str, n: int) -> list[Article]:
        return self._arxiv_query(f"all:{query}", n)

    def _arxiv_author(self, query: str, n: int) -> list[Article]:
        parts = query.strip().split()
        if len(parts) == 1:
            return self._arxiv_query(f"au:{parts[0]}", n)
        # Try original order, then reversed (arXiv stores "Last, First")
        orig = "_".join(parts)
        rev  = "_".join(parts[-1:] + parts[:-1])
        results = self._arxiv_query(f"au:{orig}", n)
        if len(results) < 2:
            results2 = self._arxiv_query(f"au:{rev}", n)
            seen = {a.url for a in results}
            results += [a for a in results2 if a.url not in seen]
        return results[:n]

    def _arxiv_query(self, search_query: str, n: int) -> list[Article]:
        resp = _SESSION.get(
            "https://export.arxiv.org/api/query",
            params={"search_query": search_query, "max_results": n, "sortBy": "relevance"},
            timeout=20,
        )
        resp.raise_for_status()

        ns  = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(resp.text)
        arts = []

        for entry in root.findall("a:entry", ns):
            title  = (entry.findtext("a:title", "", ns) or "").strip().replace("\n", " ")
            authors = [
                a.findtext("a:name", "", ns)
                for a in entry.findall("a:author", ns)
            ]
            published = entry.findtext("a:published", "", ns)
            year = published[:4] if published else ""

            url = ""
            for link in entry.findall("a:link", ns):
                if link.get("type") == "text/html" or link.get("rel") == "alternate":
                    url = link.get("href", "")
                    break
            if not url:
                url = entry.findtext("a:id", "", ns) or ""

            if title:
                arts.append(Article(title=title, authors=authors,
                                    url=url, year=year, source="arXiv"))
        return arts

    # ── PubMed ─────────────────────────────────────────────────────────────

    def _pubmed_topic(self, query: str, n: int) -> list[Article]:
        return self._pubmed_query(query, n)

    def _pubmed_author(self, query: str, n: int) -> list[Article]:
        return self._pubmed_query(f"{query}[Author]", n)

    def _pubmed_query(self, term: str, n: int) -> list[Article]:
        # Шаг 1: получаем список PMID
        r1 = _SESSION.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": term, "retmax": n, "retmode": "json"},
            timeout=20,
        )
        r1.raise_for_status()
        ids = r1.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        time.sleep(0.35)  # лимит NCBI: 3 запроса/сек

        # Шаг 2: получаем детали
        r2 = _SESSION.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
            timeout=30,
        )
        r2.raise_for_status()

        root = ET.fromstring(r2.text)
        arts = []

        for art in root.findall(".//PubmedArticle"):
            citation = art.find("MedlineCitation")
            if citation is None:
                continue
            art_node = citation.find("Article")
            if art_node is None:
                continue

            title = (art_node.findtext("ArticleTitle") or "").strip()

            authors = []
            for a in art_node.findall("AuthorList/Author"):
                last  = a.findtext("LastName") or ""
                fore  = a.findtext("ForeName") or ""
                if last:
                    authors.append(f"{last} {fore}".strip())

            pub = citation.find(".//PubDate")
            year = (pub.findtext("Year") or "") if pub is not None else ""

            pmid = citation.findtext("PMID") or ""
            url  = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            if title:
                arts.append(Article(title=title, authors=authors,
                                    url=url, year=year, source="PubMed"))
        return arts

    # ── Semantic Scholar ────────────────────────────────────────────────────

    def _ss_topic(self, query: str, n: int) -> list[Article]:
        time.sleep(1.1)  # SS rate-limit: 1 req/sec без API ключа
        resp = _SESSION.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query":  query,
                "limit":  min(n, 100),
                "fields": "title,authors,year,externalIds,openAccessPdf",
            },
            timeout=20,
        )
        resp.raise_for_status()
        return [self._ss_paper(p) for p in resp.json().get("data", []) if p.get("title")]

    def _ss_author(self, query: str, n: int) -> list[Article]:
        time.sleep(1.1)
        # Шаг 1: найти автора
        r1 = _SESSION.get(
            "https://api.semanticscholar.org/graph/v1/author/search",
            params={"query": query, "fields": "name", "limit": 3},
            timeout=15,
        )
        r1.raise_for_status()
        authors = r1.json().get("data", [])
        if not authors:
            return []

        author_id = authors[0].get("authorId")
        if not author_id:
            return []

        time.sleep(1.0)  # лимит SS: 1 запрос/сек без ключа

        # Шаг 2: статьи автора
        r2 = _SESSION.get(
            f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers",
            params={
                "fields": "title,authors,year,externalIds,openAccessPdf",
                "limit":  min(n, 100),
            },
            timeout=20,
        )
        r2.raise_for_status()
        return [self._ss_paper(p) for p in r2.json().get("data", []) if p.get("title")]

    def _ss_paper(self, item: dict) -> Article:
        title   = item.get("title") or ""
        authors = [a.get("name", "") for a in item.get("authors", [])]
        year    = str(item.get("year") or "")
        ext     = item.get("externalIds") or {}

        if item.get("openAccessPdf"):
            url = item["openAccessPdf"].get("url", "")
        elif ext.get("ArXiv"):
            url = f"https://arxiv.org/abs/{ext['ArXiv']}"
        elif ext.get("DOI"):
            url = f"https://doi.org/{ext['DOI']}"
        elif item.get("paperId"):
            url = f"https://www.semanticscholar.org/paper/{item['paperId']}"
        else:
            url = ""

        return Article(title=title, authors=authors,
                       url=url, year=year, source="Semantic Scholar")
