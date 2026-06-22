import re
from pathlib import Path
from typing import NamedTuple

_STOPWORDS = {
    # Russian
    'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а',
    'то', 'все', 'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же',
    'вы', 'за', 'бы', 'по', 'только', 'ее', 'мне', 'было', 'вот', 'от',
    'меня', 'еще', 'нет', 'о', 'из', 'ему', 'теперь', 'когда', 'даже',
    'ну', 'вдруг', 'ли', 'если', 'уже', 'или', 'ни', 'быть', 'был',
    'него', 'до', 'вас', 'нибудь', 'опять', 'уж', 'вам', 'ведь', 'там',
    'потом', 'себя', 'ничего', 'ей', 'может', 'они', 'тут', 'где',
    'есть', 'надо', 'ней', 'для', 'мы', 'тебя', 'их', 'чем', 'была',
    'сам', 'чтоб', 'без', 'будто', 'чего', 'раз', 'тоже', 'себе',
    'под', 'будет', 'ж', 'тогда', 'кто', 'этот', 'того', 'потому',
    'этого', 'какой', 'совсем', 'ним', 'здесь', 'этом', 'один', 'почти',
    'мой', 'тем', 'чтобы', 'нее', 'сейчас', 'были', 'куда', 'зачем',
    'всех', 'никогда', 'можно', 'при', 'два', 'об', 'другой', 'хоть',
    'после', 'над', 'больше', 'тот', 'через', 'эти', 'нас', 'про',
    'всего', 'них', 'какая', 'много', 'разве', 'три', 'эту', 'моя',
    'впрочем', 'свою', 'этой', 'перед', 'иногда', 'лучше', 'чуть',
    'том', 'нельзя', 'такой', 'им', 'более', 'всегда', 'конечно',
    'всю', 'между', 'также', 'этих', 'такие', 'таких', 'такое',
    'где', 'уже', 'который', 'которые', 'которых', 'которому',
    'которой', 'которого', 'это', 'себе', 'своих', 'своего',
    # English
    'the', 'and', 'or', 'is', 'in', 'on', 'at', 'to', 'for', 'of',
    'with', 'a', 'an', 'be', 'by', 'are', 'was', 'were', 'has', 'have',
    'it', 'its', 'as', 'from', 'not', 'but', 'we', 'our', 'they',
    'their', 'can', 'which', 'who', 'also', 'than', 'into', 'these',
    'those', 'this', 'that', 'been', 'will', 'would', 'could', 'should',
    'may', 'might', 'such', 'more', 'most', 'each', 'both', 'all',
    'some', 'any', 'about', 'up', 'out', 'if', 'so', 'do', 'did',
    'does', 'had', 'his', 'her', 'him', 'she', 'he', 'you', 'your',
    'are', 'what', 'when', 'where', 'how', 'while', 'then',
}

# режем текст — Ollama начинает глючить на очень длинных запросах
_MAX_EMBED_CHARS = 6_000


class CompareResult(NamedTuple):
    semantic_score: float       # cosine similarity 0..1
    common_keywords: list[str]
    only_a: list[str]
    only_b: list[str]
    word_count_a: int
    word_count_b: int


def extract_text(file_path: str | None, content: str | None = None) -> str:
    if content:
        return content
    if not file_path:
        return ""
    path = Path(file_path)
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from core.pdf_handler import PDFHandler
        h = PDFHandler()
        h.open(str(path))
        text = h.get_all_text()
        h.close()
        return text
    if suffix in (".docx", ".doc"):
        try:
            from docx import Document
            return "\n".join(p.text for p in Document(str(path)).paragraphs)
        except Exception:
            return ""
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def extract_keywords(text: str, top_n: int = 30) -> set[str]:
    words = re.findall(r'\b[а-яёa-z]{4,}\b', text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w not in _STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq, key=lambda w: freq[w], reverse=True)
    return set(ranked[:top_n])


def compare_documents(text_a: str, text_b: str, top_keywords: int = 30) -> CompareResult:
    from core.embedder import Embedder
    emb = Embedder()
    vec_a = emb.embed(text_a[:_MAX_EMBED_CHARS])
    vec_b = emb.embed(text_b[:_MAX_EMBED_CHARS])
    score = emb.similarity(vec_a, vec_b)

    kw_a = extract_keywords(text_a, top_keywords)
    kw_b = extract_keywords(text_b, top_keywords)

    return CompareResult(
        semantic_score=score,
        common_keywords=sorted(kw_a & kw_b),
        only_a=sorted(kw_a - kw_b),
        only_b=sorted(kw_b - kw_a),
        word_count_a=len(text_a.split()),
        word_count_b=len(text_b.split()),
    )
