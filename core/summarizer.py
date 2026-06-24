import requests
from requests.exceptions import ConnectionError as _ConnErr, Timeout as _Timeout, HTTPError as _HTTPError


class Summarizer:
    DEFAULT_URL   = "http://localhost:11434"
    DEFAULT_MODEL = "qwen2.5:3b"
    CHUNK_SIZE    = 4500   # символов на чанк
    MAX_CHUNKS    = 10     # не гоним в merge больше 10 выжимок

    _SYSTEM = (
        "Ты — эксперт по анализу научных текстов. "
        "Всегда отвечай на русском языке. "
        "Пиши точно и лаконично, используй только факты из текста. "
        "Не додумывай и не добавляй то, чего нет в источнике."
    )

    def __init__(self, model: str | None = None, url: str | None = None,
                 temperature: float = 0.1):
        self.model       = model or self.DEFAULT_MODEL
        self.url         = (url or self.DEFAULT_URL).rstrip("/")
        self.temperature = temperature

    def summarize(self, text: str) -> str:
        chunks = self._split(text)
        summaries = [self._summarize_chunk(i, c, len(chunks))
                     for i, c in enumerate(chunks, 1)]
        if len(summaries) == 1:
            return summaries[0]
        return self._merge(summaries[:self.MAX_CHUNKS])

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def _split(self, text: str) -> list[str]:
        """Разбивает по абзацам, не разрезая слова посередине."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks, cur = [], ""
        for para in paragraphs:
            if len(cur) + len(para) + 2 <= self.CHUNK_SIZE:
                cur = (cur + "\n\n" + para).strip()
            else:
                if cur:
                    chunks.append(cur)
                if len(para) > self.CHUNK_SIZE:
                    for i in range(0, len(para), self.CHUNK_SIZE):
                        chunks.append(para[i:i + self.CHUNK_SIZE])
                    cur = ""
                else:
                    cur = para
        if cur:
            chunks.append(cur)
        return chunks or [text[:self.CHUNK_SIZE]]

    def _summarize_chunk(self, idx: int, chunk: str, total: int) -> str:
        part = f" (часть {idx}/{total})" if total > 1 else ""
        prompt = (
            f"Выдели 3–4 ключевых утверждения из фрагмента научного текста{part}.\n"
            "Каждое утверждение — одно самодостаточное предложение.\n\n"
            f"ФРАГМЕНТ:\n{chunk}\n\n"
            "УТВЕРЖДЕНИЯ:"
        )
        return self._call(prompt, max_tokens=220)

    def _merge(self, summaries: list[str]) -> str:
        combined = "\n".join(f"• {s}" for s in summaries)
        prompt = (
            "Напиши связное итоговое резюме научной статьи на 5–7 предложений.\n"
            "Используй только факты из приведённых выжимок. "
            "Соблюдай логическую последовательность.\n\n"
            f"ВЫЖИМКИ:\n{combined}\n\n"
            "РЕЗЮМЕ:"
        )
        return self._call(prompt, max_tokens=500)

    def extract_article_metadata(self, text: str) -> dict:
        """Извлекает название, авторов и год публикации из текста статьи."""
        sample = text[:3000]
        prompt = (
            "Извлеки метаданные из начала научной статьи.\n"
            "Отвечай строго в формате (если информация не найдена — пропусти строку):\n"
            "НАЗВАНИЕ: <полное название статьи>\n"
            "АВТОРЫ: <фамилии и инициалы через запятую>\n"
            "ГОД: <четырёхзначный год, только цифры>\n\n"
            f"ТЕКСТ:\n{sample}\n\n"
            "НАЗВАНИЕ:"
        )
        try:
            raw = "НАЗВАНИЕ:" + self._call(prompt, max_tokens=250)
            meta = {"title": "", "authors": "", "year": ""}
            for line in raw.splitlines():
                line = line.strip()
                up = line.upper()
                if up.startswith("НАЗВАНИЕ:"):
                    meta["title"] = line.split(":", 1)[1].strip()
                elif up.startswith("АВТОРЫ:"):
                    meta["authors"] = line.split(":", 1)[1].strip()
                elif up.startswith("ГОД:"):
                    raw_year = line.split(":", 1)[1].strip()
                    import re
                    m = re.search(r"\b(19|20)\d{2}\b", raw_year)
                    meta["year"] = m.group(0) if m else ""
            return meta
        except Exception:
            return {"title": "", "authors": "", "year": ""}

    def _call(self, prompt: str, max_tokens: int) -> str:
        try:
            resp = requests.post(
                f"{self.url}/api/generate",
                json={
                    "model":   self.model,
                    "system":  self._SYSTEM,
                    "prompt":  prompt,
                    "stream":  False,
                    "options": {
                        "temperature":    self.temperature,
                        "num_predict":    max_tokens,
                        "repeat_penalty": 1.1,
                        "top_p":          0.9,
                    },
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            if "response" not in data:
                raise RuntimeError(f"Ollama: неожиданный ответ — {list(data.keys())}")
            return data["response"].strip()
        except _ConnErr:
            raise ConnectionError(f"Ollama недоступна: {self.url}")
        except _Timeout:
            raise TimeoutError(f"Ollama не ответила за 120 с (модель: {self.model})")
        except _HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            raise RuntimeError(f"Ollama HTTP {code} — проверьте, что модель '{self.model}' загружена")
