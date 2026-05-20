import numpy as np
import requests
from requests.exceptions import ConnectionError as _ConnErr, Timeout as _Timeout, HTTPError as _HTTPError


class Embedder:
    _BASE    = "http://localhost:11434"
    _MODEL   = "nomic-embed-text"
    _TIMEOUT = 10

    def embed(self, text: str) -> list[float]:
        try:
            r = requests.post(
                f"{self._BASE}/api/embeddings",
                json={"model": self._MODEL, "prompt": text},
                timeout=self._TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            if "embedding" not in data:
                raise ValueError(
                    f"Модель '{self._MODEL}' не установлена. "
                    f"Выполните: ollama pull {self._MODEL}"
                )
            return data["embedding"]
        except _ConnErr:
            raise ConnectionError("Ollama недоступна: http://localhost:11434")
        except _Timeout:
            raise TimeoutError(f"Ollama не ответила за {self._TIMEOUT} с")
        except _HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            if code == 404:
                raise ValueError(
                    f"Модель '{self._MODEL}' не найдена. "
                    f"Выполните: ollama pull {self._MODEL}"
                )
            raise RuntimeError(f"Ollama HTTP {code}")

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self._BASE}/api/tags", timeout=self._TIMEOUT)
            if r.status_code != 200:
                return False
            models = [m["name"] for m in r.json().get("models", [])]
            return any(self._MODEL in m for m in models)
        except Exception:
            return False

    def similarity(self, a: list[float], b: list[float]) -> float:
        va = np.array(a, dtype=np.float32)
        vb = np.array(b, dtype=np.float32)
        na = np.linalg.norm(va)
        nb = np.linalg.norm(vb)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(va, vb) / (na * nb))

    @staticmethod
    def serialize(embedding: list[float]) -> bytes:
        return np.array(embedding, dtype=np.float32).tobytes()

    @staticmethod
    def deserialize(blob: bytes) -> list[float]:
        return np.frombuffer(blob, dtype=np.float32).tolist()
