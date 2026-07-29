"""Fachada pública de la Red jurídica legacy operativa."""

from app.graph.public import LegacyLegalNetworkFacade
from app.schemas.hpn_graph import HpnGraphProjection

__all__ = ["HpnGraphProjection", "LegacyLegalNetworkFacade"]
