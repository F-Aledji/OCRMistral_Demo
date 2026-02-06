# =============================================================================
# ROUTER: DOCUMENTS (Hub)
# =============================================================================
# Aggregiert alle modularen Router für Dokument-Verwaltung.
# 
# Struktur:
# - upload.py      → POST /documents
# - queue.py       → GET /documents, GET /documents/{id}, GET /documents/{id}/file
# - claiming.py    → POST /documents/{id}/claim, POST /documents/{id}/release
# - annotations.py → GET/PUT /documents/{id}/annotations, POST .../annotated-pdf
# - processing.py  → POST /documents/{id}/process
# =============================================================================

from fastapi import APIRouter

from . import upload
from . import queue
from . import claiming
from . import annotations
from . import processing

# Haupt-Router erstellen
router = APIRouter()

# Sub-Router einbinden (alle unter /documents)
router.include_router(upload.router)
router.include_router(queue.router)
router.include_router(claiming.router)
router.include_router(annotations.router)
router.include_router(processing.router)
