# =============================================================================
# FASTAPI MAIN (Einstiegspunkt)
# =============================================================================
# Das ist die Hauptdatei der API.
# Hier werden alle Teile zusammengebaut und der Server konfiguriert.
# =============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Lokale Imports
from .db import create_db_and_tables
from .routers import documents


# -----------------------------------------------------------------------------
# APP ERSTELLEN
# -----------------------------------------------------------------------------

app = FastAPI(
    title=" WS OCR Document Review API",
    description="Backend für das Multi-User Dokument-Review System",
    version="0.1.0"
)


# -----------------------------------------------------------------------------
# CORS: Cross-Origin Resource Sharing
# -----------------------------------------------------------------------------
# Damit das Frontend (localhost:3000) mit dem Backend (localhost:8000) reden kann.
# Ohne CORS würde der Browser die Requests blockieren.
# -----------------------------------------------------------------------------

origins = [
    "http://localhost:3000",      # Next.js Dev Server
    "http://127.0.0.1:3000",
    "http://localhost:3001",      # Next.js alternative port
    "http://localhost:3002",      # Next.js alternative port
    "http://localhost:5173",      # Vite Dev Server (falls verwendet)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Erlaubt Zugriff von jeder IP im Netzwerk
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# STARTUP: Wird beim Start des Servers ausgeführt
# -----------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    """Initialisierung beim Server-Start."""
    # 1. Datenbank-Tabellen erstellen
    create_db_and_tables()
    
    # 2. Data-Ordner erstellen (für PDF-Uploads)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    print("✓ API gestartet")


# -----------------------------------------------------------------------------
# ROOT ENDPOINT (Health Check)
# -----------------------------------------------------------------------------

@app.get("/")
def read_root():
    """Einfacher Health-Check: Gibt zurück, ob die API läuft."""
    return {
        "status": "running",
        "message": "OCR Document Review API läuft!",
        "docs": "Öffne /docs für die interaktive Dokumentation"
    }


# -----------------------------------------------------------------------------
# ROUTER EINBINDEN
# -----------------------------------------------------------------------------
# Alle Endpoints aus documents.py werden unter /api/v1/... verfügbar.
# Beispiel: POST /api/v1/documents
# -----------------------------------------------------------------------------

app.include_router(
    documents.router,
    prefix="/api/v1",
    tags=["documents"]
)
