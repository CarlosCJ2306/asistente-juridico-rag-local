"""Sanitización compartida de nombres y marcadores de fuentes locales."""

from __future__ import annotations

import html
import re
import unicodedata


UNTRUSTED_MARKER_PATTERN = re.compile(
    r"(?:\[\s*(?:f\s*-?\s*\d+|fuente\s+\d+)\s*\]?"
    r"|\[\s*(?:f|fuente)\s*\]"
    r"|\[\s*(?:f|fuente)\s*(?=$|[\r\n.,;:!?]))",
    flags=re.IGNORECASE,
)


def neutralize_untrusted_markers(value: str) -> str:
    """Neutraliza sintaxis de fuente no controlada sin alterar citas legales."""

    return UNTRUSTED_MARKER_PATTERN.sub(
        lambda match: match.group(0).replace("[", "［").replace("]", "］"),
        value,
    )


def sanitize_document_name(
    value: object,
    *,
    max_length: int,
    fallback: str = "documento.pdf",
) -> str:
    """Obtiene un basename Unicode, sin controles ni HTML ejecutable."""

    if not isinstance(value, str):
        return fallback
    cleaned = "".join(
        character
        for character in value.replace("\x00", "")
        if not unicodedata.category(character).startswith("C")
    )
    basename = cleaned.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not basename or basename in {".", ".."}:
        return fallback
    escaped = html.escape(neutralize_untrusted_markers(basename), quote=True)
    limited = escaped[:max_length].strip()
    return limited or fallback
