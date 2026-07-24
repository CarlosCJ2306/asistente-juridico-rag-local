"""Endpoint de disponibilidad del backend."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["asistente-juridico-backend"]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Confirma que el proceso HTTP está disponible."""

    return HealthResponse(status="ok", service="asistente-juridico-backend")
