"""Limpieza conservadora y determinista de texto jurídico extraído."""

from __future__ import annotations

import re


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_REPEATED_SPACES = re.compile(r"[ \t]+")
_EXCESSIVE_BLANKS = re.compile(r"\n{3,}")


def clean_text(raw_text: str) -> str:
    """Conserva contenido y estructura, corrigiendo solo ruido de extracción."""

    normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _CONTROL_CHARACTERS.sub("", normalized)
    lines = [_REPEATED_SPACES.sub(" ", line).strip() for line in normalized.split("\n")]
    return _EXCESSIVE_BLANKS.sub("\n\n", "\n".join(lines)).strip()
