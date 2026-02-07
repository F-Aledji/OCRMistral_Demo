# =============================================================================
# PROCESS TRACE MODELS
# =============================================================================
# Tabellen für die Prozess-Nachverfolgung und KPI-Dashboard.
# Diese Tabellen speichern alle Verarbeitungs-Daten für:
# - Streamlit Dashboard
# - Qlik Sense
# - Historische Auswertungen
# =============================================================================

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum
from decimal import Decimal
from sqlalchemy import event, text
import json


# =============================================================================
# ENUMS
# =============================================================================

class FinalStatus(str, Enum):
    """Endstatus nach der Verarbeitung."""
    ARCHIVED = "archived"       # Erfolgreich → 99_Archive
    QUARANTINE = "quarantine"   # Fehler → 98_Error
    ESCALATED = "escalated"     # Niedriger Score → Frontend Queue


class PenaltyCategory(str, Enum):
    """Kategorien für Penalties (für Gruppierung in Dashboards)."""
    MISSING_FIELD = "missing_field"     # Pflichtfeld fehlt
    WRONG_TYPE = "wrong_type"           # Falscher Dokumenttyp
    MATH_ERROR = "math_error"           # Rechenfehler
    DATE_ERROR = "date_error"           # Datumsfehler
    REASONING = "reasoning"             # Kein/schlechtes Reasoning
    VALIDATION = "validation"           # Sonstige Validierungsfehler
    OTHER = "other"


# =============================================================================
# PROCESSING RUN (Haupttabelle)
# =============================================================================

class ProcessingRun(SQLModel, table=True):
    """
    Ein Eintrag pro PDF-Verarbeitung durch batch_runner.
    
    Speichert Metadaten zur Verarbeitung: Zeit, Modelle, Erfolg.
    Ein PDF kann mehrere Dokumente (BA-Nummern) enthalten.
    """
    __tablename__ = "processing_run"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    # Datei-Info
    filename: str = Field(index=True)
    file_size_bytes: Optional[int] = None
    page_count: Optional[int] = None
    is_scanned: bool = Field(default=False, description="True wenn Dokument gescannt ist (kein Text-Layer)")
    
    # Zeitstempel
    started_at: datetime = Field(default_factory=datetime.now, index=True)
    finished_at: Optional[datetime] = Field(default=None, index=True)
    duration_ms: Optional[int] = None
    
    # Ergebnis
    success: bool = Field(default=False, index=True)
    error_message: Optional[str] = None
    final_status: FinalStatus = Field(default=FinalStatus.ARCHIVED, index=True)
    
    # Konfiguration (für Reproduzierbarkeit)
    pipeline_mode: str = Field(default="Direct JSON")  # "Direct JSON" oder "Classic"
    ocr_model: Optional[str] = None  # z.B. "gemini-3-flash-preview"
    llm_model: Optional[str] = None  # z.B. "gemini-3-pro" (Judge)
    
    # Rohdaten (optional, für Debugging)
    raw_markdown: Optional[str] = None
    raw_json: Optional[str] = None  # JSON als String gespeichert
    reasoning_text: Optional[str] = None
    
    # =========================================================================
    # REPAIR TRACKING (für KPI-Dashboard)
    # =========================================================================
    # Schema Repair (bisherige Judge-Logik bei Validierungsfehlern)
    schema_repair_attempted: bool = Field(default=False, description="Wurde Schema-Reparatur versucht?")
    schema_repair_success: bool = Field(default=False, description="War Schema-Reparatur erfolgreich?")
    
    # Business Repair (neue Logik bei schlechtem Score)
    business_repair_attempted: bool = Field(default=False, description="Wurde Business-Reparatur versucht?")
    business_repair_success: bool = Field(default=False, description="War Business-Reparatur erfolgreich?")
    initial_score: Optional[int] = Field(default=None, description="Score VOR Business Repair")
    final_score: Optional[int] = Field(default=None, description="Score NACH Business Repair")
    score_improvement: Optional[int] = Field(default=None, description="Score-Verbesserung durch Business Repair")
    
    
    # Relationship: Ein Run hat 0-n extrahierte Dokumente
    documents: List["ExtractedDocument"] = Relationship(
        back_populates="run",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


# =============================================================================
# EXTRACTED DOCUMENT (Pro BA-Nummer)
# =============================================================================

class ExtractedDocument(SQLModel, table=True):
    """
    Ein Eintrag pro extrahiertes Dokument (BA-Nummer) aus dem PDF.
    
    Wenn ein PDF 3 AB's enthält, gibt es 3 Einträge hier.
    """
    __tablename__ = "extracted_document"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    run_id: UUID = Field(foreign_key="processing_run.id", index=True)
    
    # Position im JSON
    document_index: int = Field(default=0)
    
    # Extrahierte Werte
    ba_number: Optional[str] = Field(default=None, index=True)
    vendor_number: Optional[str] = Field(default=None, index=True)
    vendor_name: Optional[str] = None
    document_date: Optional[datetime] = None
    document_type: Optional[str] = Field(default=None, index=True)  # "AB", "Rechnung", etc.
    net_total: Optional[float] = None
    position_count: Optional[int] = None
    
    # Score
    score: int = Field(default=100, index=True)
    initial_score: Optional[int] = Field(default=None, description="Score vor Business Repair (falls durchgeführt)")
    needs_review: bool = Field(default=False, index=True)
    has_template: bool = Field(default=False, description="True wenn für diesen Lieferanten ein Template existiert")
    
    # Output
    xml_output: Optional[str] = None
    
    # Timestamps (für Frontend-Queue)
    created_at: datetime = Field(default_factory=datetime.now)
    
    # Optional: Frontend-Verknüpfung (wenn eskaliert)
    frontend_document_id: Optional[UUID] = Field(
        default=None,
        foreign_key="documents.id",
        index=True,
        description="Verknüpfung zum Frontend-Dokument bei Eskalation"
    )
    
    # Timestamps
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column_kwargs={"onupdate": datetime.now}
    )
    
    # Relationships
    run: ProcessingRun = Relationship(back_populates="documents")
    penalties: List["ScorePenalty"] = Relationship(
        back_populates="document",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    signals: List["ScoreSignal"] = Relationship(
        back_populates="document",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


# =============================================================================
# SCORE PENALTY (Punktabzüge)
# =============================================================================

class ScorePenalty(SQLModel, table=True):
    """
    Ein Eintrag pro Punktabzug.
    
    Beispiel: "-20 Punkte: BA-Nummer fehlt"
    """
    __tablename__ = "score_penalty"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    document_id: UUID = Field(foreign_key="extracted_document.id", index=True)
    
    points: int  # Abgezogene Punkte (positiv, z.B. 20)
    reason: str = Field(index=True)  # "BA-Nummer fehlt"
    category: PenaltyCategory = Field(default=PenaltyCategory.OTHER, index=True)
    
    # Relationship
    document: ExtractedDocument = Relationship(back_populates="penalties")


# =============================================================================
# SCORE SIGNAL (Positive Info)
# =============================================================================

class ScoreSignal(SQLModel, table=True):
    """
    Ein Eintrag pro positivem Signal (Info, keine Punkte).
    
    Beispiel: "INFO: Reasoning erkannt"
    """
    __tablename__ = "score_signal"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    document_id: UUID = Field(foreign_key="extracted_document.id", index=True)
    
    signal: str  # "Reasoning erkannt"
    is_bonus: bool = Field(default=False)  # War es ein Bonuspunkt?
    bonus_points: Optional[int] = None
    
    # Relationship
    document: ExtractedDocument = Relationship(back_populates="signals")


# =============================================================================
# HELPER: Penalty-Kategorisierung
# =============================================================================

def categorize_penalty(reason: str) -> PenaltyCategory:
    """
    Ordnet einen Penalty-Grund einer Kategorie zu.
    
    Wird beim Speichern aufgerufen, um Penalties zu gruppieren.
    """
    reason_lower = reason.lower()
    
    if "fehlt" in reason_lower or "missing" in reason_lower:
        return PenaltyCategory.MISSING_FIELD
    elif "dokumenttyp" in reason_lower or "falscher" in reason_lower:
        return PenaltyCategory.WRONG_TYPE
    elif "summe" in reason_lower or "math" in reason_lower or "berechnung" in reason_lower:
        return PenaltyCategory.MATH_ERROR
    elif "datum" in reason_lower or "date" in reason_lower:
        return PenaltyCategory.DATE_ERROR
    elif "reasoning" in reason_lower:
        return PenaltyCategory.REASONING
    else:
        return PenaltyCategory.OTHER
