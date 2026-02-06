# =============================================================================
# DATENBANK-VERBINDUNG (db.py)
# =============================================================================
# Diese Datei kümmert sich um:
# 1. Verbindung zur SQLite-Datenbank
# 2. Erstellen der Tabellen beim Start
# 3. Session-Management (für API-Requests)
# =============================================================================

import os
from sqlmodel import create_engine, SQLModel, Session

# Importiere alle Models, damit SQLModel sie kennt
from .db_models import Document, DocumentFile, Annotation
from .trace_models import ProcessingRun, ExtractedDocument, ScorePenalty, ScoreSignal


# -----------------------------------------------------------------------------
# DATENBANK-PFAD
# -----------------------------------------------------------------------------
# Wir speichern die Datenbank im backend/-Ordner als "demo.db".
# os.path funktioniert auf Windows UND Mac/Linux gleich!
# -----------------------------------------------------------------------------

# __file__ = Pfad zu dieser Datei (db.py)
# dirname zweimal = backend/app → backend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "demo.db")

# SQLite URL-Format: sqlite:///pfad/zur/datei.db
# Die drei Slashes sind wichtig!
DATABASE_URL = f"sqlite:///{DB_PATH}"


# -----------------------------------------------------------------------------
# ENGINE: Die Verbindung zur Datenbank
# -----------------------------------------------------------------------------
# check_same_thread=False: Erlaubt Zugriff von mehreren Threads
# (FastAPI ist async und nutzt mehrere Threads)
# -----------------------------------------------------------------------------

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False},
    echo=False  # Auf True setzen um SQL-Queries zu sehen (Debug)
)


# -----------------------------------------------------------------------------
# TABELLEN ERSTELLEN
# -----------------------------------------------------------------------------
# Diese Funktion wird beim Start der App aufgerufen.
# Sie erstellt alle Tabellen, falls sie noch nicht existieren.
# -----------------------------------------------------------------------------

def create_db_and_tables():
    """Erstellt alle Tabellen in der Datenbank."""
    SQLModel.metadata.create_all(engine)
    print(f"✓ Datenbank bereit: {DB_PATH}")


# -----------------------------------------------------------------------------
# SESSION: Für jeden API-Request eine eigene "Sitzung"
# -----------------------------------------------------------------------------
# FastAPI nutzt "Dependency Injection": 
# Wir geben get_session als Parameter an und FastAPI ruft es automatisch auf.
#
# Beispiel in einem Endpoint:
#   def list_documents(session: Session = Depends(get_session)):
#       return session.exec(select(Document)).all()
# -----------------------------------------------------------------------------

def get_session():
    """
    Erzeugt eine Datenbank-Session für einen Request.
    
    'yield' bedeutet: Die Session wird zurückgegeben, der Code pausiert,
    und nach dem Request wird die Session automatisch geschlossen.
    """
    with Session(engine) as session:
        yield session
