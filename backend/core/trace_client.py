# =============================================================================
# TRACE INTEGRATION
# =============================================================================
# Einfaches Interface für batch_runner.py zum Speichern in die Datenbank.
# 
# Verwenden in batch_runner.py:
#   from backend.trace import save_trace
#   save_trace(filename, result)
# =============================================================================

import os
import sys

# Backend zu sys.path hinzufügen (eine Ebene hoch von "core")

# Note: 'backend' package must be in sys.path (e.g. running from project root)


# Datenbank initialisieren (Tabellen erstellen falls nötig)
from backend.app.db import create_db_and_tables, engine
from backend.app.services.trace_service import save_processing_run

# Tabellen beim Import erstellen
create_db_and_tables()


def save_trace(
    filename: str,
    result_data: dict,
    pipeline_mode: str = "Direct JSON",
    ocr_model: str = None,
    llm_model: str = None,
    started_at=None,
    escalation_threshold: int = 85,
    source_file_path: str = None
):
    """
    Speichert Verarbeitungsdaten in die Trace-Datenbank.
    
    Args:
        filename: Name der PDF-Datei
        result_data: Ergebnis von PipelineController.process_document()
        pipeline_mode: "Direct JSON" oder "Classic"
        ocr_model: z.B. "gemini-3-flash-preview"
        llm_model: z.B. "gemini-3-pro"
        started_at: Startzeitpunkt
        escalation_threshold: Score unter dem eskaliert wird
        source_file_path: Pfad zur Original-Datei (für Kopie ins Frontend)
    
    Example:
        from backend.trace import save_trace
        
        result = controller.process_document(file_path)
        save_trace(filename, result, ocr_model=cfg.GEMINI_OCR_MODEL, source_file_path=file_path)
    """
    return save_processing_run(
        filename=filename,
        result_data=result_data,
        pipeline_mode=pipeline_mode,
        ocr_model=ocr_model,
        llm_model=llm_model,
        started_at=started_at,
        escalation_threshold=escalation_threshold,
        source_file_path=source_file_path
    )
