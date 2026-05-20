from __future__ import annotations
import re
import requests
from requests.exceptions import ConnectionError as _ConnErr, Timeout as _Timeout, HTTPError as _HTTPError


class Translator:
    DEFAULT_URL   = "http://localhost:11434"
    DEFAULT_MODEL = "qwen2.5:3b"
    CHUNK_SIZE    = 1800   # символов на чанк при переводе длинных текстов

    _SYSTEM_RU = (
        "Ты — профессиональный переводчик научных текстов. "
        "Переводи точно и естественно на русский язык. "
        "Сохраняй научную терминологию. "
        "Отвечай ТОЛЬКО переводом — без пояснений, без кавычек."
    )
    _SYSTEM_EN = (
        "You are a professional scientific translator. "
        "Translate accurately and naturally into English. "
        "Preserve scientific terminology. "
        "Reply with ONLY the translation — no explanations, no quotes."
    )

    def __init__(self, model: str | None = None, url: str | None = None):
        self.model = model or self.DEFAULT_MODEL
        self.url   = (url or self.DEFAULT_URL).rstrip("/")

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def detect_language(self, text: str) -> str:
        latin = sum(1 for c in text if c.isalpha() and ord(c) < 128)
        total = sum(1 for c in text if c.isalpha())
        if total == 0:
            return "en"
        return "en" if latin / total > 0.8 else "other"

    # ── Перевод на русский ──────────────────────────────────────────────────

    def translate_to_russian(self, text: str) -> str:
        """Короткий текст (заголовок) — один быстрый вызов.
        Длинный текст (статья) — побуквенная разбивка по абзацам."""
        if len(text) <= 400:
            return self._translate_short_ru(text)
        return self._translate_long(text, target="ru")

    def _translate_short_ru(self, text: str) -> str:
        prompt = (
            "Переведи на русский язык. "
            "Технические термины можно оставить на латинице.\n\n"
            "Attention Is All You Need"
            " → Внимание — это всё, что вам нужно\n"
            "Deep Residual Learning for Image Recognition"
            " → Глубокое остаточное обучение для распознавания изображений\n"
            "BERT: Pre-training of Deep Bidirectional Transformers"
            " → BERT: предобучение глубоких двунаправленных трансформеров\n\n"
            f"{text} →"
        )
        try:
            raw = self._call(prompt, max_tokens=200, system=self._SYSTEM_RU)
            return self._clean(raw) or text
        except Exception:
            return text

    # ── Перевод на английский ───────────────────────────────────────────────

    def translate_to_english(self, text: str) -> str:
        """Используется для перевода поискового запроса."""
        if self.detect_language(text) == "en":
            return text
        prompt = (
            "Переведи поисковый запрос на английский язык.\n\n"
            "нейронные сети для обработки изображений"
            " → neural networks for image processing\n"
            "машинное обучение в медицине"
            " → machine learning in medicine\n"
            "влияние климата на биоразнообразие"
            " → climate impact on biodiversity\n\n"
            f"{text} →"
        )
        try:
            raw = self._call(prompt, max_tokens=100, system=self._SYSTEM_EN)
            return self._clean(raw) or text
        except Exception:
            return text

    # ── Длинный текст: разбивка по абзацам ─────────────────────────────────

    def _translate_long(self, text: str, target: str) -> str:
        chunks = self._split_paragraphs(text)
        system = self._SYSTEM_RU if target == "ru" else self._SYSTEM_EN

        if target == "ru":
            def make_prompt(chunk: str) -> str:
                return f"Переведи на русский язык:\n\n{chunk}\n\nПЕРЕВОД:"
        else:
            def make_prompt(chunk: str) -> str:
                return f"Translate to English:\n\n{chunk}\n\nTRANSLATION:"

        parts = []
        for chunk in chunks:
            # токенов нужно примерно столько же, сколько слов в чанке × 1.4
            tokens = min(int(len(chunk.split()) * 1.4) + 80, 700)
            try:
                out = self._call(make_prompt(chunk), max_tokens=tokens, system=system)
                parts.append(out)
            except Exception:
                parts.append(chunk)   # fallback — оставляем оригинал

        return "\n\n".join(parts)

    def _split_paragraphs(self, text: str) -> list[str]:
        """Разбивает текст по абзацам, собирает в чанки ≤ CHUNK_SIZE."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks, cur = [], ""
        for para in paragraphs:
            if len(cur) + len(para) + 2 <= self.CHUNK_SIZE:
                cur = (cur + "\n\n" + para).strip()
            else:
                if cur:
                    chunks.append(cur)
                if len(para) > self.CHUNK_SIZE:
                    # Абзац больше лимита — режем по символам
                    for i in range(0, len(para), self.CHUNK_SIZE):
                        chunks.append(para[i:i + self.CHUNK_SIZE])
                    cur = ""
                else:
                    cur = para
        if cur:
            chunks.append(cur)
        return chunks or [text[:self.CHUNK_SIZE]]

    # ── Единый метод вызова API ─────────────────────────────────────────────

    def _call(self, prompt: str, max_tokens: int, system: str = "") -> str:
        body: dict = {
            "model":  self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature":    0.1,
                "num_predict":    max_tokens,
                "repeat_penalty": 1.1,
                "top_p":          0.9,
            },
        }
        if system:
            body["system"] = system
        try:
            resp = requests.post(
                f"{self.url}/api/generate",
                json=body,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if "response" not in data:
                raise RuntimeError(f"Ollama: неожиданный ответ — {list(data.keys())}")
            return data["response"].strip()
        except _ConnErr:
            raise ConnectionError(f"Ollama недоступна: {self.url}")
        except _Timeout:
            raise TimeoutError("Ollama не ответила за 30 с")
        except _HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            raise RuntimeError(f"Ollama HTTP {code} — проверьте, что модель '{self.model}' загружена")

    # ── Постобработка ───────────────────────────────────────────────────────

    @staticmethod
    def _clean(text: str) -> str:
        line = text.splitlines()[0].strip() if text else ""
        line = re.sub(r'^["\'"«»→\-]+|["\'"«»]+$', '', line).strip()
        line = re.sub(r'[一-鿿぀-ヿ가-힯]+', '', line).strip()
        line = re.sub(r' {2,}', ' ', line).strip()
        return line
