# =============================================================================
# TRACE SERVICE
# =============================================================================
# Service zum Speichern von Process Trace Daten in der Datenbank.
# Wird von batch_runner.py aufgerufen statt (oder zusätzlich zu) Dateien.
# =============================================================================

import os
import sys
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

# Projekt-Root für Imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# SQLModel Session
from sqlmodel import Session

# Lokale Models
from ..db import engine
from ..trace_models import (
    ProcessingRun, ExtractedDocument, ScorePenalty, ScoreSignal,
    FinalStatus, PenaltyCategory, categorize_penalty
)
from ..db_models import Document, DocumentStatus, DocumentFile, FileKind
from . import storage

import logging
logger = logging.getLogger(__name__)


def save_processing_run(
    filename: str,
    result_data: Dict[str, Any],
    pipeline_mode: str = "Direct JSON",
    ocr_model: str = None,
    llm_model: str = None,
    started_at: datetime = None,
    escalation_threshold: int = 85,
    source_file_path: str = None
) -> ProcessingRun:
    """
    Speichert einen Verarbeitungs-Durchlauf in der Datenbank.
    
    Args:
        filename: Name der PDF-Datei
        result_data: Ergebnis von PipelineController.process_document()
        pipeline_mode: "Direct JSON" oder "Classic"
        ocr_model: z.B. "gemini-3-flash-preview"
        llm_model: z.B. "gemini-3-pro"
        started_at: Startzeitpunkt (default: jetzt)
        escalation_threshold: Score unter dem eskaliert wird (default: 85)
        source_file_path: Pfad zur Quelldatei (um sie ins Frontend zu kopieren)
    
    Returns:
        ProcessingRun Objekt
    """

    now = datetime.now()
    started = started_at or now

    with Session(engine) as session:
        # 1. ProcessingRun erstellen
        run = ProcessingRun(
            filename=filename,
            started_at=started,
            finished_at=now,
            duration_ms=int((now - started).total_seconds() * 1000),
            success=result_data.get("success", False),
            error_message=result_data.get("error"),
            pipeline_mode=pipeline_mode,
            ocr_model=ocr_model,
            llm_model=llm_model,
            raw_markdown=result_data.get("markdown"),
            raw_json=json.dumps(result_data.get("json", {}), ensure_ascii=False) if result_data.get("json") else None,
            # Metriken
            file_size_bytes=result_data.get("file_size_bytes"),
            page_count=result_data.get("page_count"),
            is_scanned=result_data.get("is_scanned", False),
            # Repair Tracking (neu!)
            schema_repair_attempted=result_data.get("schema_repair_attempted", False),
            business_repair_attempted=result_data.get("business_repair_attempted", False),
            business_repair_success=result_data.get("business_repair_success", False),
            initial_score=result_data.get("initial_score"),
            final_score=result_data.get("avg_score")
        )
        
        # Score-Verbesserung berechnen (falls Business Repair durchgeführt wurde)
        if run.business_repair_attempted and run.initial_score is not None and run.final_score is not None:
            run.score_improvement = run.final_score - run.initial_score
            run.schema_repair_success = result_data.get("judge_repaired", False) and not run.business_repair_attempted
        
        # Final Status basierend auf Erfolg
        if not result_data.get("success"):
            run.final_status = FinalStatus.QUARANTINE
        
        session.add(run)
        session.flush()  # ID generieren
        
        # 2. Extrahierte Dokumente verarbeiten
        json_data = result_data.get("json", {})
        documents = json_data.get("documents", [])
        score_cards = result_data.get("score_cards", [])
        
        # Prüfe ob Pipeline-Ergebnis manuelle Prüfung erfordert
        # (z.B. wenn Judge-Reparatur fehlgeschlagen ist)
        needs_escalation = result_data.get("needs_manual_review", False)
        if needs_escalation:
            logger.info(f"Manuelle Prüfung angefordert für: {filename}")
        
        for idx, doc_data in enumerate(documents):
            sc = doc_data.get("SupplierConfirmation", {})
            
            # Score holen
            score_card = score_cards[idx] if idx < len(score_cards) else {}
            score = score_card.get("total_score", 100)
            
            # ExtractedDocument erstellen
            extracted = ExtractedDocument(
                run_id=run.id,
                document_index=idx,
                ba_number=_safe_get(sc, ["Correspondence", "number"]),
                vendor_number=_safe_get(sc, ["invoiceSupplierData", "SupplierPartner", "number"]),
                vendor_name=_safe_get(sc, ["invoiceSupplierData", "SupplierPartner", "name"]),
                document_date=_parse_date(_safe_get(sc, ["supplierConfirmationData", "date", "value"])),
                document_type=_safe_get(sc, ["supplierConfirmationData", "documentType"]),
                net_total=_safe_float(_safe_get(sc, ["documentNetTotal"])),
                position_count=len(sc.get("details", [])) if sc.get("details") else 0,
                score=score,
                initial_score=result_data.get("initial_score") if result_data.get("business_repair_attempted") else None,
                needs_review=(score < escalation_threshold),
                has_template=score_card.get("template_match", False)
            )
            
            # XML Output holen
            xml_content = result_data.get("xml", [])
            if isinstance(xml_content, list) and idx < len(xml_content):
                extracted.xml_output = xml_content[idx]
            elif isinstance(xml_content, str):
                extracted.xml_output = xml_content
            
            session.add(extracted)
            session.flush()
            
            # Penalties speichern
            penalties = score_card.get("penalties", [])
            for penalty_str in penalties:
                points, reason = _parse_penalty(penalty_str)
                penalty = ScorePenalty(
                    document_id=extracted.id,
                    points=points,
                    reason=reason,
                    category=categorize_penalty(reason)
                )
                session.add(penalty)
            
            # Signals speichern
            signals = score_card.get("signals", [])
            for signal_str in signals:
                is_bonus, points, text = _parse_signal(signal_str)
                signal = ScoreSignal(
                    document_id=extracted.id,
                    signal=text,
                    is_bonus=is_bonus,
                    bonus_points=points if is_bonus else None
                )
                session.add(signal)
            
            # Eskalation prüfen
            if score < escalation_threshold:
                needs_escalation = True
                # Dokument in Frontend-Queue pushen
                frontend_doc = _create_frontend_document(
                    session, extracted, filename, run.id, source_file_path
                )
                if frontend_doc:
                    extracted.frontend_document_id = frontend_doc.id
        
        # =========================================================================
        # FALLBACK: Eskalation ohne Documents
        # =========================================================================
        # Wenn needs_manual_review=True aber keine Documents im JSON sind
        # (z.B. komplett fehlgeschlagene Extraktion), trotzdem eskalieren
        
        if needs_escalation and not documents:
            logger.info(f"Fallback-Eskalation (keine Documents): {filename}")
            # Direkt ein Frontend-Dokument erstellen ohne ExtractedDocument
            _create_fallback_frontend_document(
                session, filename, run.id, source_file_path, 
                error_message=result_data.get("error")
            )
        
        # Final Status aktualisieren
        if needs_escalation:
            run.final_status = FinalStatus.ESCALATED
        elif run.success:
            run.final_status = FinalStatus.ARCHIVED
        
        session.commit()
        logger.info(f"Trace gespeichert: {filename} → {run.final_status.value}")
        
        return run


def _create_frontend_document(
    session: Session,
    extracted: ExtractedDocument,
    filename: str,
    run_id: UUID,
    source_file_path: Optional[str] = None
) -> Optional[Document]:
    """
    Erstellt ein Dokument in der Frontend-Queue für manuelle Bearbeitung.
    Kopiert dabei auch das PDF in den storage-Ordner.
    """
    try:
        # 1. Datenbank-Eintrag
        doc = Document(
            status=DocumentStatus.NEEDS_REVIEW,
            ba_number=extracted.ba_number,
            vendor_name=extracted.vendor_name,
            total_value=extracted.net_total,
            score=extracted.score,
            filename=filename
        )
        session.add(doc)
        session.commit() # Commit um ID zu bekommen
        session.refresh(doc) # Refresh um ID zu haben
        
        # 2. Datei kopieren (wichtig für Frontend-Anzeige)
        if source_file_path and os.path.exists(source_file_path):
            with open(source_file_path, "rb") as f:
                content = f.read()
            
            saved_path = storage.save_original_pdf(doc.id, content)
            
            # File-Entry erstellen
            doc_file = DocumentFile(
                document_id=doc.id,
                kind=FileKind.ORIGINAL_PDF,
                path=saved_path
            )
            session.add(doc_file)
            session.commit()
            
        logger.info(f"Eskaliert an Frontend: {extracted.ba_number or filename} (Score: {extracted.score}) - ID: {doc.id}")
        return doc
    except Exception as e:
        logger.error(f"Fehler beim Erstellen des Frontend-Dokuments: {e}")
        return None


def _create_fallback_frontend_document(
    session: Session,
    filename: str,
    run_id: UUID,
    source_file_path: Optional[str] = None,
    error_message: Optional[str] = None
) -> Optional[Document]:
    """
    Erstellt ein Frontend-Dokument für Fälle ohne ExtractedDocument.
    
    Wird verwendet wenn:
    - Validierung komplett fehlschlug (kein valides JSON)
    - Judge-Reparatur fehlgeschlagen
    - Aber Dokument trotzdem manuell geprüft werden soll
    """
    try:
        # Datenbank-Eintrag mit minimalen Daten
        doc = Document(
            status=DocumentStatus.NEEDS_REVIEW,
            filename=filename,
            score=0  # Kein Score möglich
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)
        
        # Datei kopieren
        if source_file_path and os.path.exists(source_file_path):
            with open(source_file_path, "rb") as f:
                content = f.read()
            
            saved_path = storage.save_original_pdf(doc.id, content)
            
            doc_file = DocumentFile(
                document_id=doc.id,
                kind=FileKind.ORIGINAL_PDF,
                path=saved_path
            )
            session.add(doc_file)
            session.commit()
        
        logger.info(f"Fallback-Eskalation an Frontend: {filename} - ID: {doc.id}")
        if error_message:
            logger.info(f"  Fehler: {error_message}")
        return doc
    except Exception as e:
        logger.error(f"Fehler bei Fallback-Eskalation: {e}")
        return None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _safe_get(data: dict, keys: List[str], default=None):
    """Sicher durch verschachtelte Dicts navigieren."""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return default
    return data if data is not None else default


def _safe_float(value) -> Optional[float]:
    """Konvertiert zu float oder None."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parst Datumsstring zu datetime."""
    if not date_str:
        return None
    for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _parse_penalty(penalty_str: str) -> tuple[int, str]:
    """
    Parst "-20 Punkte: BA fehlt" zu (20, "BA fehlt").
    """
    match = re.match(r"-(\d+)\s*Punkte?:\s*(.+)", penalty_str)
    if match:
        return int(match.group(1)), match.group(2).strip()
    return 0, penalty_str


def _parse_signal(signal_str: str) -> tuple[bool, int, str]:
    """
    Parst "INFO: Reasoning erkannt" zu (False, 0, "Reasoning erkannt")
    oder "+5 Punkte: Bonus" zu (True, 5, "Bonus").
    """
    # Bonus?
    match = re.match(r"\+(\d+)\s*Punkte?:\s*(.+)", signal_str)
    if match:
        return True, int(match.group(1)), match.group(2).strip()
    
    # INFO?
    if signal_str.startswith("INFO:"):
        return False, 0, signal_str[5:].strip()
    
    return False, 0, signal_str
