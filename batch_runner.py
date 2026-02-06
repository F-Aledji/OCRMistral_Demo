# =============================================================================
# BATCH RUNNER - Automatische Hotfolder-Verarbeitung
# =============================================================================
#
# ZWECK:
# Überwacht einen Input-Ordner und verarbeitet PDFs automatisch durch die
# OCR-Pipeline. Dies ermöglicht "Drop & Go" Verarbeitung ohne manuelle Arbeit.
#
# ORDNERSTRUKTUR (konfiguriert in config/config.py):
# ┌─────────────────┐
# │ 01_INPUT        │  ← PDFs hier ablegen zur Verarbeitung
# └────────┬────────┘
#          │ Pipeline verarbeitet
#          ▼
# ┌─────────────────┐   ┌─────────────────┐
# │ 02_OUTPUT       │   │ 03_PROCESS_TRACE│  ← JSON, XML, Logs pro Datei
# │ (XML-Dateien)   │   │ (Debugging)     │
# └────────┬────────┘   └─────────────────┘
#          │
#          ▼
# ┌─────────────────┐   ┌─────────────────┐
# │ 04_ARCHIVE      │   │ 98_ERROR        │  ← Bei Fehlern
# │ (Erfolgreich)   │   │ (Quarantäne)    │
# └─────────────────┘   └─────────────────┘
#
# ABLAUF (Endlosschleife):
# 1. Scanne Input-Ordner nach PDFs
# 2. Für jede PDF: OCR → Validierung → Scoring → XML
# 3. Bei Erfolg: XML nach Output, PDF nach Archive
# 4. Bei Fehler: PDF nach Error-Quarantäne
# 5. Warte X Sekunden, dann zurück zu 1.
#
# FEHLERBEHANDLUNG:
# - AUTH-Fehler (401/403): Runner stoppt sofort
# - Rate-Limits (429): Wartet und versucht erneut
# - Sonstige Fehler: Datei → Quarantäne
#
# USAGE:
#   python batch_runner.py
#   (Beenden mit STRG+C)
#
# =============================================================================

import os
import shutil
import time
import json
import logging
from datetime import datetime

# Config & Logging
import config.config as cfg

# Unified Pipeline importieren (ersetzt PipelineController)
from core.pipeline import UnifiedPipeline

# Logging Setup
logger = cfg.setup_logging("BatchRunner")

# -----------------------------------------------------------------------------
# TRACE DATENBANK
# -----------------------------------------------------------------------------
# Speichert Verarbeitungsdaten in SQLite für KPI-Dashboard und Analyse.
# Falls das Backend-Modul nicht verfügbar ist, läuft der Runner trotzdem.

try:
    from backend.trace import save_trace
    TRACE_DB_ENABLED = True
    logger.info("✓ Trace-Datenbank aktiviert")
except ImportError as e:
    TRACE_DB_ENABLED = False
    logger.warning(f"Trace-DB nicht verfügbar: {e}")

# =============================================================================
# SETUP & HILFSFUNKTIONEN
# =============================================================================

def setup_folders():
    """
    Erstellt alle notwendigen Ordner beim Start.
    
    Iteriert über cfg.FOLDERS und erstellt fehlende Verzeichnisse.
    Externe Laufwerke (z.B. Netzwerk) werden bei Fehler übersprungen.
    """
    for name, path in cfg.FOLDERS.items():
        if not os.path.exists(path):
            try:
                os.makedirs(path)
                logger.info(f"Ordner erstellt: {path}")
            except OSError as e:
                # Externe Laufwerke (z.B. J:) sind evtl. nicht verfügbar
                logger.warning(f"Ordner '{name}' ({path}) konnte nicht erstellt werden: {e}")


def _safe_filename_fragment(value: str) -> str:
    """
    Bereinigt einen String für sichere Dateinamen.
    
    - Ersetzt deutsche Umlaute (ä→ae, ö→oe, etc.)
    - Entfernt Sonderzeichen (nur alphanumerisch + -_. erlaubt)
    
    Beispiel: "Gemini-2.0-Flash (Preview)" → "Gemini-2.0-Flash_Preview"
    """
    # Deutsche Umlaute ersetzen
    replacement = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}
    for search_for_replacement, target in replacement.items():
        value = value.replace(search_for_replacement, target)

    # Nur sichere Zeichen behalten
    return "".join(
        c if c.isalnum() or c in ("-", "_", ".") else "_"
        for c in value
    ).strip("_")

# Falls mehere BA_Nummern pro BA Nummer ein Reasoning Text
def _extract_reasoning_texts(result_data):
    """Extrahiert Reasoning-Texte je Dokument aus dem JSON (string oder liste)."""
    try:
        docs = result_data.get("json", {}).get("documents", [])
        per_doc_texts = []
        for doc in docs:
            reasoning = (
                doc.get("SupplierConfirmation", {})
                .get("reasoning")
            )
            if reasoning is None:
                per_doc_texts.append([])
                continue
            if isinstance(reasoning, list):
                per_doc_texts.append([str(x).strip() for x in reasoning if str(x).strip()])
            else:
                text = str(reasoning).strip()
                per_doc_texts.append([text] if text else [])
        return per_doc_texts
    except Exception:
        return []


def save_process_trace(filename, result_data, reasoning_model_name: str = None):
    """Speichert die Prozessdaten ((optional Markdown), JSON, XML) in den Trace Ordner für die Nachverfolgung."""
    try:
        # Dateinamen ohne Endung holen
        base_name = os.path.splitext(filename)[0]

        # Unterordner erstellen im 03_Process_Trace -> beispiel 03_Process_Trace/<filename>/
        trace_dir = os.path.join(cfg.FOLDERS["TRACE"], base_name)
        os.makedirs(trace_dir,exist_ok=True) #True schaut ob der Ordner schon existiert

        #1. markdown speicher (RAW)
        if "markdown" in result_data:
            with open(os.path.join(trace_dir, "1_raw_markdown.md"), "w", encoding="utf-8") as f: # w steht für write damit die datei erstellt wird
                f.write(result_data["markdown"])

        #2. Extracted JSON speichern (formatted)
        if "json" in result_data:
            with open(os.path.join(trace_dir, "2_extracted_data.json"), "w", encoding="utf-8") as f:
                json.dump(result_data["json"], f, indent=4, ensure_ascii=False)

        #2b. Reasoning separat speichern (falls vorhanden)
        reasoning_by_doc = _extract_reasoning_texts(result_data)
        if reasoning_by_doc:
            model_name = reasoning_model_name or cfg.GEMINI_OCR_MODEL
            model_fragment = _safe_filename_fragment(model_name or "unknown")
            for idx, texts in enumerate(reasoning_by_doc):
                if not texts:
                    continue
                suffix = f"_{idx}" if len(reasoning_by_doc) > 1 else ""
                reasoning_path = os.path.join(
                    trace_dir,
                    f"reasoning_{model_fragment}{suffix}.txt"
                )
                with open(reasoning_path, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(texts))

        #3 XML speichern
        if "xml" in result_data:
            xml_content = result_data["xml"]
            # Checken ob Liste (Mehrere Dokumente) oder String (Einzel/Error)
            if isinstance(xml_content, list):
                for idx, xml_str in enumerate(xml_content):
                    # Bei Liste hängen wir Index an: 3_final_0.xml, 3_final_1.xml
                    suffix = f"_{idx}" if len(xml_content) > 1 else ""
                    with open(os.path.join(trace_dir, f"3_final{suffix}.xml"), "w", encoding="utf-8") as f:
                        f.write(xml_str)
            else:
                # String Fallback
                with open(os.path.join(trace_dir, "3_final.xml"), "w", encoding="utf-8") as f:
                    f.write(xml_content)

        #3b ScoreCards speichern (falls vorhanden)
        score_cards = result_data.get("score_cards")
        if isinstance(score_cards, list) and score_cards:
            for idx, card in enumerate(score_cards):
                suffix = f"_{idx}" if len(score_cards) > 1 else ""
                score_path = os.path.join(trace_dir, f"4_score_card{suffix}.json")
                with open(score_path, "w", encoding="utf-8") as f:
                    json.dump(card, f, indent=4, ensure_ascii=False)

        #4 Log schreiben
        status_msg = "Success" if result_data.get("success", False) else "Failed"
        error_info = f"\nError: {result_data.get('error', 'Unknown Error')}" if not result_data.get("success", False) else ""
        
        with open(os.path.join(trace_dir, "process_log.txt"), "w", encoding="utf-8") as f:
            f.write(f"Processed on: {datetime.now().isoformat()}\n")
            f.write(f"Filename: {filename}\n")
            f.write(f"Status: {status_msg}{error_info}\n")
    except Exception as e:
        logger.error(f"Fehler beim Speichern der Prozessdaten für {filename}: {e}")

def safe_move_file(src_path, dest_folder):
    """Verschiebt eine Datei sicher in den Zielordner. Versucht es bei PermissionError (Datei blockiert) kurz erneut."""
    
    if not os.path.exists(src_path):
        return

    filename = os.path.basename(src_path)
    dest_path = os.path.join(dest_folder, filename)

    # 1. Kollision prüfen und Dateinamen anpassen (z.B. datei_20241010_120000.pdf)
    if os.path.exists(dest_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        new_filename = f"{name}_{timestamp}{ext}"
        dest_path = os.path.join(dest_folder, new_filename)
        logger.info(f"Datei existiert bereits im Ziel. Umbenannt zu: {new_filename}")

    # 2. Verschieben mit Retry Logic (für PermissionError) also falls die Datei noch von einem anderen Prozess genutzt wird
    max_retries = 3
    for attempt in range(max_retries):
        try:
            shutil.move(src_path, dest_path)
            return
        except PermissionError:
            if attempt < max_retries - 1:
                logger.warning(f"Datei {filename} ist gesperrt. Warte 6s... (Versuch {attempt+1}/{max_retries})")
                time.sleep(6)
            else:
                logger.error(f"Konnte Datei nicht verschieben (Zugriff verweigert): {filename}")
                # Wir lassen sie im Input liegen, damit sie nicht verloren geht, aber loggen den Fehler.
        except Exception as e:
            logger.error(f"Kritischer Fehler beim Verschieben von {filename}: {e}")
            return


def main():
    """Hauptfunktion des Batch Runners. Startet die Überwachung und Verarbeitung."""
    logger.info("--Starte Batch Verarbeitung--")
    setup_folders() #Ordner erstellen wenn nicht vorhanden

    # Prüfe ob GEMINI_PROJECT_ID gesetzt ist
    if not cfg.GEMINI_PROJECT_ID:
        logger.error("GEMINI_PROJECT_ID nicht zu finden. Die Variable muss in der .env Datei gesetzt sein.")
        return
    
    # UnifiedPipeline initialisieren (handhabt OCR-Engine intern)
    pipeline = UnifiedPipeline(
        enable_judge=True,
        enable_xml=True,
        quarantine_dir=cfg.FOLDERS["ERROR"]
    )

    logger.info(f"Überwachung aktiviert für Ordner: {cfg.FOLDERS['INPUT']}")
    logger.info(f"Judge Provider: {cfg.JUDGE_PROVIDER} mit Modell: {cfg.JUDGE_MODEL}")
    logger.info("===================================")
    logger.info("Drücke STRG+C zum Beenden.")
    logger.info("===================================")

    # --- Main Loop ---
    waiting_message_shown = False
    try:
        while True:
            # Scanne ordner nach PDFs (nicht case-sensitiv)
            files =[f for f in os.listdir(cfg.FOLDERS["INPUT"]) if f.lower().endswith(".pdf")]

            if not files: 
                if not waiting_message_shown:
                    logger.info("Keine weiteren Dateien. Warte auf Input...")
                    waiting_message_shown = True
                time.sleep(cfg.POLLING_INTERVAL)  # Warte X Sekunden bevor erneut geprüft wird
                continue
            
            waiting_message_shown = False
            for filename in files:
                file_path = os.path.join(cfg.FOLDERS["INPUT"], filename)

                # Checke ob die Datei noch geschrieben wird (Größe 0 oder gesperrt)
                try: 
                    if os.path.getsize(file_path) == 0:
                        continue # Datei ist leer, daher überspringen
                except OSError:
                    continue

                logger.info(f"Verarbeite Datei: {filename}")

                # ----- PIPELINE VERARBEITUNG ------
                pipeline_result = pipeline.process_file(file_path, pipeline_mode="Direct JSON")
                result = pipeline_result.to_dict()  # Konvertiere zu Dict für Kompatibilität

                if result["success"]:
                    # A. Output XML
                    xml_content = result["xml"]
                    base_xml_name = os.path.splitext(filename)[0]

                    if isinstance(xml_content, list):
                         for idx, xml_str in enumerate(xml_content):
                            # Suffix beim Output Ordner
                            suffix = f"_{idx+1}" if len(xml_content) > 1 else ""
                            xml_filename = f"{base_xml_name}{suffix}.xml"
                            with open(os.path.join(cfg.FOLDERS["OUTPUT"], xml_filename), "w", encoding="utf-8") as f:
                                f.write(xml_str)
                    else:
                        # String Fallback
                        xml_filename = base_xml_name + ".xml"
                        with open(os.path.join(cfg.FOLDERS["OUTPUT"], xml_filename), "w", encoding="utf-8") as f:
                            f.write(xml_content)

                    # B. Prozess Trace speichern (Dateien - deprecated)
                    save_process_trace(filename, result, reasoning_model_name=cfg.GEMINI_OCR_MODEL)
                    
                    # B2. Trace in Datenbank speichern (neu)
                    if TRACE_DB_ENABLED:
                        save_trace(
                            filename=filename,
                            result_data=result,
                            pipeline_mode="Direct JSON",
                            ocr_model=cfg.GEMINI_OCR_MODEL,
                            llm_model=cfg.JUDGE_MODEL,
                            source_file_path=file_path
                        )

                    # C. Datei in Archiv verschieben
                    safe_move_file(file_path, cfg.FOLDERS["ARCHIVE"])
                    logger.info(f"Erfolgreich verarbeitet: {filename} - XML erstellt und gespeichert")

                else:
                    error_msg = str(result['error'])
                    
                    # 1. Check auf AUTH Fehler (401/403) -> SOFORT STOPPEN
                    if "401" in error_msg or "403" in error_msg or "Unauthenticated" in error_msg or "PermissionDenied" in error_msg:
                        logger.critical(f"KRITISCHER AUTH-FEHLER: {error_msg}")
                        logger.critical("Der Runner wird beendet, um weitere Probleme zu vermeiden. Bitte API-Key/Service Account prüfen.")
                        return # Beendet die main() Funktion und damit das Skript
                    
                    # 2. Check auf RETRY Fehler (429, 500, 503, Timeout) -> WARTEN
                    # 429 = Quota, 5xx = Server Error, Timeout = Verbindung
                    if any(x in error_msg for x in ["429", "RESOURCE_EXHAUSTED", "quota", "500", "503", "InternalServerError", "ServiceUnavailable", "Timeout", "ConnectionError"]):
                        wait_time = cfg.RETRY_WAIT_SECONDS
                        logger.warning(f"Temporäres API/Netzwerk-Problem ({error_msg}).") 
                        logger.warning(f"Datei bleibt im Input. Warte {wait_time} Sekunden und versuche es erneut...")
                        time.sleep(wait_time)
                        continue # Nächste Iteration = Retry
                    
                    # 3. Sonstige Fehler (Leeres JSON, Bad Request 400, Parse Error) -> QUARANTÄNE
                    logger.warning(f"Fehler bei der Verarbeitung von {filename}: {error_msg}")

                     # Auch im Fehlerfall Trace Daten speichern (Dateien - deprecated)
                    save_process_trace(filename, result, reasoning_model_name=cfg.GEMINI_OCR_MODEL)
                    
                    # Trace in Datenbank speichern (auch bei Fehler)
                    if TRACE_DB_ENABLED:
                        save_trace(
                            filename=filename,
                            result_data=result,
                            pipeline_mode="Direct JSON",
                            ocr_model=cfg.GEMINI_OCR_MODEL,
                            llm_model=cfg.JUDGE_MODEL,
                            source_file_path=file_path
                        )

                    # Verschieben nach Error Quarantine
                    safe_move_file(file_path, cfg.FOLDERS["ERROR"])

                    # Log schreiben
                    error_destination = os.path.join(cfg.FOLDERS["ERROR"], filename)
                    with open(error_destination + ".txt", "w", encoding="utf-8") as f:
                        f.write(f"Zeitpunkt: {datetime.now()}\nError: {error_msg}\n")


    except KeyboardInterrupt:
        logger.info("Beende Runner ...") # für Strg +C abbruch


if __name__ == "__main__":
    main() # wenn die Datei direkt ausgeführt wird, starte main