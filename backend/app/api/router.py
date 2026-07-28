"""Composición central de rutas públicas."""

from fastapi import APIRouter

from app.api.routes.documents import router as documents_router
from app.api.routes.document_processing import router as document_processing_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.hpn import router as hpn_router
from app.api.routes.hpn_graph import router as hpn_graph_router
from app.api.routes.models import router as models_router
from app.api.routes.search import router as search_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(models_router)
api_router.include_router(document_processing_router)
api_router.include_router(documents_router)
api_router.include_router(search_router)
api_router.include_router(chat_router)
api_router.include_router(hpn_router)
api_router.include_router(hpn_graph_router)
