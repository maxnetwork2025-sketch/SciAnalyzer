import io
from pathlib import Path

import fitz  # pymupdf
from PIL import Image


class PDFHandler:
    def __init__(self):
        self._doc: fitz.Document | None = None

    def open(self, file_path: str) -> int:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        self._doc = fitz.open(str(path))
        return len(self._doc)

    def get_page_image(self, page_num: int, dpi: int = 150) -> Image.Image:
        page = self._doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        return Image.open(io.BytesIO(pix.tobytes("png")))

    def get_page_text(self, page_num: int) -> str:
        return self._doc[page_num].get_text()

    def get_all_text(self) -> str:
        return "\n".join(page.get_text() for page in self._doc)

    def close(self):
        if self._doc is not None:
            self._doc.close()
            self._doc = None

    def is_open(self) -> bool:
        return self._doc is not None
