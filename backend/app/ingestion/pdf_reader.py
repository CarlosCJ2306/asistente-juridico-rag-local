"""Lectura local y segura de PDFs mediante PyMuPDF."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

import fitz  # type: ignore[import-untyped]

from app.core.paths import DOCUMENTS_DIR, PROJECT_ROOT


@dataclass(frozen=True)
class PdfPageText:
    page_number: int
    raw_text: str


class PdfReadError(RuntimeError):
    """Error controlado de lectura cuyo código puede exponerse de forma segura."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def resolve_document_path(
    relative_path: str,
    *,
    documents_directory: Path = DOCUMENTS_DIR,
    project_root: Path = PROJECT_ROOT,
) -> Path:
    """Resuelve una ruta persistida sin permitir salida de storage/documents."""

    normalized = relative_path.replace("\\", "/")
    source = Path(normalized)
    windows_path = PureWindowsPath(relative_path)
    if source.is_absolute() or windows_path.is_absolute() or windows_path.drive or ".." in source.parts:
        raise PdfReadError("PDF_PATH_INVALID")
    candidate = (project_root.resolve() / source).resolve()
    allowed = documents_directory.resolve()
    try:
        candidate.relative_to(allowed)
    except ValueError as exc:
        raise PdfReadError("PDF_PATH_INVALID") from exc
    if not candidate.exists():
        raise PdfReadError("PDF_FILE_NOT_FOUND")
    if not candidate.is_file():
        raise PdfReadError("PDF_PATH_INVALID")
    return candidate


def read_pdf_pages(path: Path) -> list[PdfPageText]:
    """Extrae todas las páginas ordenadas y cierra siempre el documento."""

    try:
        with fitz.open(path) as pdf:
            if pdf.needs_pass:
                raise PdfReadError("PDF_ENCRYPTED")
            return [
                PdfPageText(page_number=index, raw_text=_extract_page_text(page))
                for index, page in enumerate(pdf, start=1)
            ]
    except PdfReadError:
        raise
    except (fitz.FileDataError, RuntimeError, OSError) as exc:
        raise PdfReadError("PDF_UNREADABLE") from exc


def _extract_page_text(page: Any) -> str:
    """Reconstruye líneas desde palabras posicionadas, sin inferir contenido."""

    words = page.get_text("words", sort=True)
    if not words:
        return page.get_text("text", sort=True)

    lines: list[tuple[float, int, list[str]]] = []
    for word in words:
        _, y0, _, _, text, block_number, _, _ = word
        if not text:
            continue
        if lines and abs(y0 - lines[-1][0]) <= 1.0:
            lines[-1][2].append(text)
        else:
            lines.append((y0, block_number, [text]))
    if not lines:
        return page.get_text("text", sort=True)

    rendered: list[str] = []
    previous_block: int | None = None
    for _, block_number, line_words in lines:
        if rendered:
            rendered.append("\n\n" if block_number != previous_block else "\n")
        rendered.append(" ".join(line_words))
        previous_block = block_number
    return "".join(rendered)
