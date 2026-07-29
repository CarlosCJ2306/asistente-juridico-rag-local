"""Identidad invitada mediante cookie opaca; no implementa autenticación."""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from typing import Literal

from fastapi import Request, Response

from app.core.config import settings


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")
_COOKIE_PATH = "/api"


@dataclass(frozen=True)
class ConversationPrincipal:
    owner_type: Literal["guest", "account"]
    guest_session_hash: str | None = None
    user_id: str | None = None

    @classmethod
    def guest(cls, session_hash: str) -> "ConversationPrincipal":
        return cls(owner_type="guest", guest_session_hash=session_hash)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _valid_token(value: object) -> str | None:
    return value if isinstance(value, str) and _TOKEN_PATTERN.fullmatch(value) else None


def get_conversation_principal(
    request: Request,
    response: Response,
) -> ConversationPrincipal:
    """Obtiene o crea una sesión invitada sin exponer su token en JSON."""

    token = _valid_token(request.cookies.get(settings.conversation_cookie_name))
    if token is None:
        token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=settings.conversation_cookie_name,
        value=token,
        max_age=settings.conversation_guest_retention_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.conversation_cookie_secure,
        samesite="lax",
        path=_COOKIE_PATH,
    )
    return ConversationPrincipal.guest(_token_hash(token))
