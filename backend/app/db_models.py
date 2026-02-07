# =============================================================================
# DATENBANK-MODELLE (SQLModel)
# =============================================================================
# Diese Datei definiert die Tabellen für unsere SQLite-Datenbank.
# SQLModel kombiniert SQLAlchemy (Datenbank) mit Pydantic (Validierung).
# =============================================================================

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from sqlmodel import Field, SQLModel, Relationship, Column
from sqlalchemy import JSON, event, text


# -----------------------------------------------------------------------------
# ENUMS: Definieren erlaubte Werte für bestimmte Felder
# -----------------------------------------------------------------------------

class DocumentStatus(str, Enum):
    """
    Status eines Dokuments in der Warteschlange.
    Der Status ändert sich im Laufe der Verarbeitung.
    """
    NEW = "NEW"                         # Gerade hochgeladen, noch nicht verarbeitet
    OCR_RUNNING = "OCR_RUNNING"         # OCR läuft gerade
    OCR_DONE = "OCR_DONE"               # OCR fertig, wartet auf Review
    NEEDS_REVIEW = "NEEDS_REVIEW"       # Muss manuell geprüft werden (Score zu niedrig)
    NEEDS_REVIEW_BA = "NEEDS_REVIEW_BA" # BA-Nummer fehlt oder ungültig
    HEALED = "HEALED"                   # Wurde manuell korrigiert
    VALID = "VALID"                     # Alles OK, bereit für Export
    ERROR = "ERROR"                     # Technischer Fehler aufgetreten
    EXPORTED = "EXPORTED"               # An ERP exportiert


class FileKind(str, Enum):
    """
    Typ einer gespeicherten Datei.
    Pro Dokument können mehrere Dateien existieren.
    """
    ORIGINAL_PDF = "ORIGINAL_PDF"       # Das Original vom Lieferanten
    ANNOTATED_PDF = "ANNOTATED_PDF"     # PDF mit eingezeichneten Boxen
    XML_EXPORT = "XML_EXPORT"           # Generierte XML für SAP


# -----------------------------------------------------------------------------
# TABELLE: documents
# -----------------------------------------------------------------------------
# Das ist die Haupttabelle - jeder Eintrag ist ein Dokument in der Queue.
# Hier speichern wir auch Claiming-Infos (wer bearbeitet gerade?).
# -----------------------------------------------------------------------------

class Document(SQLModel, table=True):
    """
    Haupttabelle: Ein Eintrag pro hochgeladenem Dokument.
    
    Beispiel:
        Document(
            id="abc-123",
            status="NEEDS_REVIEW",
            ba_number="BA123456",
            vendor_name="Lieferant GmbH",
            claimed_by_user_id="alice"  # Alice bearbeitet gerade
        )
    """
    __tablename__ = "documents"
    # Primärschlüssel: UUID statt Auto-Increment (besser für verteilte Systeme)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    
    # Status in der Warteschlange
    status: DocumentStatus = Field(default=DocumentStatus.NEW, index=True)
    
    # Extrahierte Daten (für Übersicht in Queue-Liste)
    ba_number: Optional[str] = Field(default=None, index=True, description="Extrahierte BA-Nummer")
    vendor_name: Optional[str] = Field(default=None, description="Extrahierter Lieferantenname")
    total_value: Optional[float] = Field(default=None, description="Extrahierte Gesamtsumme")
    score: Optional[int] = Field(default=None, description="Score aus der Validierung (0-100)")
    
    # Neu: Original-Dateiname
    filename: Optional[str] = Field(default=None, description="Original-Dateiname")
    
    # Claiming: Wer bearbeitet dieses Dokument gerade?
    claimed_by_user_id: Optional[str] = Field(default=None, index=True, description="User-ID des Bearbeiters")
    claim_expires_at: Optional[datetime] = Field(default=None, index=True, description="Wann läuft die Sperre ab?")
    
    # Optimistic Locking: Verhindert, dass zwei User gleichzeitig speichern
    # Jedes Speichern erhöht die Version. Client muss aktuelle Version mitsenden.
    version: int = Field(default=1)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column_kwargs={"onupdate": datetime.now, "server_default": text("CURRENT_TIMESTAMP")}
    )
    
    # Beziehungen zu anderen Tabellen (werden automatisch geladen)
    files: List["DocumentFile"] = Relationship(
        back_populates="document",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    annotations: List["Annotation"] = Relationship(
        back_populates="document",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    # Verknüpfung zum Lieferanten (neu)
    supplier_id: Optional[uuid.UUID] = Field(default=None, foreign_key="suppliers.id", description="Verknüpfter Lieferant")
    supplier: Optional["Supplier"] = Relationship(back_populates="documents")


# -----------------------------------------------------------------------------
# TABELLE: document_files
# -----------------------------------------------------------------------------
# Speichert Pfade zu den physischen Dateien (Original-PDF, Annotated PDF, XML).
# -----------------------------------------------------------------------------

class DocumentFile(SQLModel, table=True):
    """
    Datei-Eintrag: Verknüpft ein Dokument mit einer physischen Datei.
    
    Beispiel:
        DocumentFile(
            document_id="abc-123",
            kind="ORIGINAL_PDF",
            path="/data/abc-123/original.pdf"
        )
    """
    __tablename__ = "document_files"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    document_id: uuid.UUID = Field(foreign_key="documents.id", index=True)
    
    kind: FileKind = Field(index=True, description="Art der Datei (Original, Annotated, XML)")
    path: str = Field(description="Pfad zur Datei auf der Festplatte")
    
    created_at: datetime = Field(default_factory=datetime.now)
    
    # Rück-Beziehung zum Dokument
    document: Document = Relationship(back_populates="files")


# -----------------------------------------------------------------------------
# TABELLE: annotations
# -----------------------------------------------------------------------------
# Speichert die Bounding-Boxen und extrahierten Werte.
# Jedes Speichern erstellt einen neuen Eintrag (History).
# -----------------------------------------------------------------------------

class Annotation(SQLModel, table=True):
    """
    Annotation: Speichert extrahierte Felder mit Bounding-Boxen.
    
    Das 'fields'-Feld ist ein JSON-Objekt mit der Struktur:
    {
        "ba_number": {
            "value": "BA123456",
            "bbox": {"page": 0, "x0": 100, "y0": 200, "x1": 180, "y1": 212}
        },
        "total": {
            "value": 1234.56,
            "bbox": {"page": 0, "x0": 400, "y0": 500, "x1": 480, "y1": 512}
        }
    }
    """
    __tablename__ = "annotations"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    document_id: uuid.UUID = Field(foreign_key="documents.id", index=True)
    
    # Wer hat diese Annotation erstellt?
    author_user_id: Optional[str] = Field(default=None, index=True)
    source: str = Field(default="model", index=True, description="'model' = KI, 'user' = Mensch")
    
    # Die eigentlichen Daten als JSON
    # sa_column=Column(JSON) sagt SQLModel, dass es JSON-Daten speichern soll
    fields: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    
    # Version: Passt zur Document-Version für Konsistenz
    version: int = Field(default=1)
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column_kwargs={"onupdate": datetime.now}
    )
    
    # Rück-Beziehung
    document: Document = Relationship(back_populates="annotations")


# -----------------------------------------------------------------------------
# TABELLE: valid_ba_numbers (Simulation Produktive DB)
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# TABELLE: suppliers (Neu: Stammdaten)
# -----------------------------------------------------------------------------
class Supplier(SQLModel, table=True):
    """
    Stammdaten: Lieferanten.
    Hier werden die Lieferanten verwaltet, um Templates zuzuordnen.
    """
    __tablename__ = "suppliers"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True, description="Name des Lieferanten")
    supplier_code: str = Field(index=True, unique=True, description="ERP-Nummer (z.B. 7000123)")
    
    # Kontakt / Info (Erweiterbar)
    contact_email: Optional[str] = Field(default=None)
    
    # Beziehungen
    template: Optional["SupplierTemplate"] = Relationship(back_populates="supplier")
    documents: List["Document"] = Relationship(back_populates="supplier")

# -----------------------------------------------------------------------------
# TABELLE: valid_ba_numbers (Simulation Produktive DB)
# -----------------------------------------------------------------------------
class ValidBANumber(SQLModel, table=True):
    """
    Simulation der produktiven Datenbank.
    Enthält gültige BA-Nummern und zugehörige Lieferanten.
    """
    __tablename__ = "valid_ba_numbers"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ba_number: str = Field(index=True, unique=True)
    supplier_name: str = Field(index=True)
    supplier_id: str = Field(index=True) # Verweis auf ERP-ID

# -----------------------------------------------------------------------------
# TABELLE: supplier_templates (Overlay)
# -----------------------------------------------------------------------------
class SupplierTemplate(SQLModel, table=True):
    """
    Speichert Koordinaten-Templates für Lieferanten.
    Wird genutzt wenn BA-Nummer einem Lieferanten zugeordnet werden kann.
    """
    __tablename__ = "supplier_templates"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    
    # Änderung: Jetzt Verknüpfung zur Supplier-Tabelle via UUID
    supplier_id: uuid.UUID = Field(foreign_key="suppliers.id", unique=True)
    
    # JSON mit Koordinaten für Header, Footer, Table
    # Bsp: {"header_bbox": [0, 0, 100, 50], ...}
    coordinates_json: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))

    # Beziehung
    supplier: "Supplier" = Relationship(back_populates="template")
