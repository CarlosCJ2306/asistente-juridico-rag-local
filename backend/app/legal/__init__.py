"""Fachada pública del HPN legacy operativo."""

from app.legal.public import LegacyHpnFacade
from app.schemas.hpn import HpnMatrixDetail

__all__ = ["HpnMatrixDetail", "LegacyHpnFacade"]
