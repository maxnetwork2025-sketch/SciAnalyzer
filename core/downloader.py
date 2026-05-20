"""
Загрузка научных статей по URL.
  arXiv  → PDF  (конвертируем /abs/ → /pdf/)
  PubMed → TXT  (EFetch abstract в plain-text)
  Semantic Scholar → PDF если прямая ссылка, иначе TXT
"""
from __future__ import annotations
import re
from pathlib import Path

import requests

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "SciAnalyzer/1.0"

from core.paths import DOWNLOAD_DIR


def _sanitize(text: str, maxlen: int = 60) -> str:
    text = re.sub(r'[\\/:*?"<>|]', '_', text).replace('\n', ' ').strip()
    return text[:maxlen].rstrip('_. ')


def download_article(url: str, title: str, source: str, year: str) -> str:
    """
    Скачивает статью и сохраняет в НайденныеСтатьи/.
    Возвращает абсолютный путь к файлу. Бросает исключение при ошибке.
    """
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    base = _sanitize(f"{source}_{year}_{title}")

    if source == "arXiv":
        return _download_arxiv(url, base)
    elif source == "PubMed":
        return _download_pubmed(url, base)
    elif source == "CyberLeninka":
        return _download_cyberleninka(url, base)
    elif source == "SibAC":
        return _download_sibac(url, base)
    elif source in ("CyberPedia", "МолодойУчёный", "eLibrary"):
        return _download_generic(url, base)
    else:
        return _download_generic(url, base)


# ── arXiv ──────────────────────────────────────────────────────────────────

def _download_arxiv(url: str, base: str) -> str:
    pdf_url = url.replace("/abs/", "/pdf/")
    path = DOWNLOAD_DIR / (base + ".pdf")
    _stream_to_file(pdf_url, path)
    return str(path)


# ── PubMed ─────────────────────────────────────────────────────────────────

def _download_pubmed(url: str, base: str) -> str:
    m = re.search(r'/(\d+)/?$', url)
    if not m:
        raise ValueError(f"Не удалось извлечь PMID из URL: {url}")
    pmid = m.group(1)

    r = _SESSION.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
        params={"db": "pubmed", "id": pmid, "rettype": "abstract", "retmode": "text"},
        timeout=20,
    )
    r.raise_for_status()

    disclaimer = (
        "\n\n" + "─" * 60 + "\n"
        "ПРИМЕЧАНИЕ: PubMed предоставляет только аннотацию (abstract).\n"
        "Полный текст статьи доступен на сайте издателя по DOI или через\n"
        "институциональный доступ. Ссылка: https://pubmed.ncbi.nlm.nih.gov/"
        + pmid + "/\n"
    )
    path = DOWNLOAD_DIR / (base + ".txt")
    path.write_text(r.text + disclaimer, encoding="utf-8")
    return str(path)


# ── CyberLeninka ───────────────────────────────────────────────────────────

def _download_cyberleninka(url: str, base: str) -> str:
    """
    Скачивает статью с CyberLeninka.
    Стратегия:
      1. Ищет прямую ссылку на PDF на странице статьи.
      2. Если нашёл — скачивает PDF.
      3. Иначе — сохраняет аннотацию + ссылку как TXT.
    """
    from bs4 import BeautifulSoup

    page_r = _SESSION.get(url, timeout=20)
    page_r.raise_for_status()
    soup = BeautifulSoup(page_r.text, "html.parser")

    # Ищем ссылку на PDF (CyberLeninka хранит PDF на том же домене)
    pdf_url = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.endswith(".pdf") or "/pdf" in href.lower():
            pdf_url = href if href.startswith("http") else f"https://cyberleninka.ru{href}"
            break

    # Также проверяем <meta> og:pdf или data-url
    if not pdf_url:
        for tag in soup.find_all("meta"):
            prop = tag.get("property", "") or tag.get("name", "")
            if "pdf" in prop.lower():
                pdf_url = tag.get("content", "")
                break

    if pdf_url:
        try:
            path = DOWNLOAD_DIR / (base + ".pdf")
            _stream_to_file(pdf_url, path)
            return str(path)
        except Exception:
            pass

    # Fallback: сохраняем аннотацию как TXT
    title_tag = soup.find("h1")
    title     = title_tag.get_text(strip=True) if title_tag else ""

    abstract = ""
    for sel in [".abstract", "[itemprop='description']", "p.text-main"]:
        tag = soup.select_one(sel)
        if tag:
            abstract = tag.get_text(strip=True)
            break

    text = (
        f"Источник: CyberLeninka\n"
        f"Страница: {url}\n\n"
        + (f"Название: {title}\n\n" if title else "")
        + (f"Аннотация:\n{abstract}\n\n" if abstract else "")
        + "─" * 60 + "\n"
        "ПРИМЕЧАНИЕ: PDF не найден на странице статьи.\n"
        "Полный текст может быть доступен по ссылке выше.\n"
    )
    path = DOWNLOAD_DIR / (base + ".txt")
    path.write_text(text, encoding="utf-8")
    return str(path)


# ── SibAC ──────────────────────────────────────────────────────────────────

def _download_sibac(url: str, base: str) -> str:
    """
    Скачивает выпуск журнала/сборника с sibac.info, содержащий статью.
    Стратегия:
      1. Открывает страницу статьи (allow_redirects=False обязателен).
      2. Ищет ссылки на PDF выпуска в блоке .sib-article/.page_inform,
         затем по всей странице. Берёт первую ссылку.
      3. Скачивает PDF выпуска.
      4. Если PDF не найден — сохраняет аннотацию как TXT.
    """
    from bs4 import BeautifulSoup

    page_r = _SESSION.get(url, timeout=20, allow_redirects=False)
    page_r.raise_for_status()
    soup = BeautifulSoup(page_r.text, "html.parser")

    def _find_pdf_url(scope) -> str | None:
        for a in scope.find_all("a", href=True):
            href = a["href"]
            if "/archive/" in href and href.lower().endswith(".pdf"):
                return href if href.startswith("http") else f"https://sibac.info{href}"
        return None

    # Сначала ищем в cite-блоке, потом по всей странице
    pdf_url = None
    cite_block = soup.select_one(".sib-article") or soup.select_one(".page_inform")
    if cite_block:
        pdf_url = _find_pdf_url(cite_block)
    if not pdf_url:
        pdf_url = _find_pdf_url(soup)

    if pdf_url:
        try:
            path = DOWNLOAD_DIR / (base + "_выпуск.pdf")
            _stream_to_file(pdf_url, path)
            return str(path)
        except Exception:
            pass

    # Fallback: сохраняем аннотацию как TXT
    title_tag = soup.select_one("h1")
    title_text = title_tag.get_text(strip=True) if title_tag else ""

    abstract = ""
    for sel in [".field-name-body .field-item", ".field-item.even"]:
        tag = soup.select_one(sel)
        if tag:
            abstract = tag.get_text(strip=True)
            break

    authors = ""
    authors_tag = soup.select_one(".authors")
    if authors_tag:
        authors = authors_tag.get_text(strip=True)

    cite_text = ""
    if cite_block:
        cite_text = cite_block.get_text(" ", strip=True)

    text = (
        f"Источник: SibAC (sibac.info)\n"
        f"Страница: {url}\n\n"
        + (f"Название: {title_text}\n\n" if title_text else "")
        + (f"Авторы: {authors}\n\n" if authors else "")
        + (f"Аннотация:\n{abstract}\n\n" if abstract else "")
        + (f"Ссылка для цитирования:\n{cite_text}\n\n" if cite_text else "")
        + "─" * 60 + "\n"
        "ПРИМЕЧАНИЕ: PDF не найден на странице статьи.\n"
        "Полный текст может быть доступен по ссылке выше.\n"
    )
    path = DOWNLOAD_DIR / (base + ".txt")
    path.write_text(text, encoding="utf-8")
    return str(path)


# ── Semantic Scholar / общий ────────────────────────────────────────────────

def _download_generic(url: str, base: str) -> str:
    if "arxiv.org/abs/" in url:
        return _download_arxiv(url, base)

    if url.endswith(".pdf") or "/pdf/" in url:
        path = DOWNLOAD_DIR / (base + ".pdf")
        _stream_to_file(url, path)
        return str(path)

    # HEAD-запрос: узнаём тип до загрузки, чтобы не тянуть PDF в память
    ct = ""
    try:
        head = _SESSION.head(url, timeout=10, allow_redirects=True)
        ct = head.headers.get("Content-Type", "")
    except Exception:
        pass

    if "pdf" in ct:
        path = DOWNLOAD_DIR / (base + ".pdf")
        _stream_to_file(url, path)
        return str(path)

    r = _SESSION.get(url, timeout=30)
    r.raise_for_status()
    ct = r.headers.get("Content-Type", "")
    if "pdf" in ct:
        path = DOWNLOAD_DIR / (base + ".pdf")
        _stream_to_file(url, path)
    else:
        path = DOWNLOAD_DIR / (base + ".txt")
        path.write_text(r.text, encoding="utf-8")
    return str(path)


# ── PDF → TXT ───────────────────────────────────────────────────────────────

def pdf_to_txt(pdf_path: str) -> str:
    """Извлекает текст из PDF через pypdf. Возвращает строку."""
    from pypdf import PdfReader
    try:
        reader = PdfReader(pdf_path)
    except Exception as e:
        raise ValueError(f"Не удалось открыть PDF: {e}") from e
    parts = []
    for i, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            parts.append(f"--- Страница {i} ---\n{text}")
    return "\n\n".join(parts)


def save_as_txt(pdf_path: str) -> str:
    """Конвертирует PDF в TXT, сохраняет рядом с PDF. Возвращает путь к TXT."""
    text = pdf_to_txt(pdf_path)
    txt_path = Path(pdf_path).with_suffix(".txt")
    txt_path.write_text(text, encoding="utf-8")
    return str(txt_path)


# ── Утилита ─────────────────────────────────────────────────────────────────

def _stream_to_file(url: str, path: Path) -> None:
    r = _SESSION.get(url, stream=True, timeout=30)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
