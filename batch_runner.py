import os
import shutil
import time
import json
import logging
from datetime import datetime

# Config & Logging
import config.config as cfg

# Klassen Importieren
from controller.pipeline_controller import PipelineController
from extraction.gemini_ocr_engine import GeminiOCR
from llm.gemini_llm import GeminiLLM
# Alternativ from llm.openai_llm import OpenAILLM

# Logging Setup
logger = cfg.setup_logging("BatchRunner")

def setup_folders():
    """Erstellt alle notwendigen Ordner beim Start."""
    for name, path in cfg.FOLDERS.items():
        if not os.path.exists(path):
            os.makedirs(path)
            logger.info(f"Ordner erstellt: {path}")

# Funktion um Daten in 03_process_trace zu speichern + für AI-korrektur
def save_process_trace(filename, result_data):
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

        #3 XML speichern
        if "xml" in result_data:
            with open(os.path.join(trace_dir, "3_final.xml"), "w", encoding="utf-8") as f:
                f.write(result_data["xml"])

        #4 Log schreiben
        status_msg = "Success" if result_data.get("success", False) else "Failed"
        error_info = f"\nError: {result_data.get('error', 'Unknown Error')}" if not result_data.get("success", False) else ""
        
        with open(os.path.join(trace_dir, "process_log.txt"), "w", encoding="utf-8") as f:
            f.write(f"Processed on: {datetime.now().isoformat()}\n")
            f.write(f"Status: {status_msg}{error_info}\n")
    except Exception as e:
        logger.error(f"Error saving process trace for {filename}: {e}")

def safe_move_file(src_path, dest_folder):
    """
    Verschiebt eine Datei sicher in den Zielordner.
    Falls der Dateiname dort schon existiert, wird ein Zeitstempel angehängt.
    Versucht es bei PermissionError (Datei blockiert) kurz erneut.
    """
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
        logger.info(f"⚠️ Datei existiert bereits im Ziel. Umbenannt zu: {new_filename}")

    # 2. Verschieben mit Retry Logic (für PermissionError)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            shutil.move(src_path, dest_path)
            return
        except PermissionError:
            if attempt < max_retries - 1:
                logger.warning(f"⏳ Datei {filename} ist gesperrt. Warte 2s... (Versuch {attempt+1}/{max_retries})")
                time.sleep(2)
            else:
                logger.error(f"❌ Konnte Datei nicht verschieben (Zugriff verweigert): {filename}")
                # Wir lassen sie im Input liegen, damit sie nicht verloren geht, aber loggen den Fehler.
        except Exception as e:
            logger.error(f"❌ Kritischer Fehler beim Verschieben von {filename}: {e}")
            return

def main():
    logger.info("--Starte Batch Verarbeitung--")
    setup_folders() #Ordner erstellen wenn nicht vorhanden
    # Einrichten der Engines
    project_root = cfg.PROJECT_ROOT

    # OCR Engine initialisieren
    if not cfg.GEMINI_PROJECT_ID:
        logger.error("GEMINI_PROJECT_ID nicht zu finden. Die Variable muss in der .env Datei gesetzt sein.")
        return
    
    ocr_engine = GeminiOCR(
        service_account_json_path=cfg.GEMINI_CREDENTIALS,
        project_id=cfg.GEMINI_PROJECT_ID,
        location=cfg.GEMINI_LOCATION
        )
    
    # 2. LLM Engine initialisieren -> hier OpenAI optional Gemini
    llm_engine = GeminiLLM(project_root) 
    # Alternativ: llm_engine = OpenAILLM(project_root) 

    # 3. Controller initialisieren
    controller = PipelineController(project_root, ocr_engine, llm_engine)

    logger.info(f"Überwachung aktiviert für Ordner: {cfg.FOLDERS['INPUT']}")
    logger.info("Drücken Sie STRG+C zum Beenden.")

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

                logger.info(f"⚡Verarbeite Datei: {filename}")

                # ----- AB HIER CODE ZUM: PIPELINE STARTEN ------
                # Mode: Classic für OCR -> Markdown -> LLM -> XML

                result = controller.process_document(file_path, pipeline_mode="Classic")

                if result["success"]:
                    # A. Output XML
                    xml_filename = os.path.splitext(filename)[0] + ".xml"
                    with open(os.path.join(cfg.FOLDERS["OUTPUT"], xml_filename), "w", encoding="utf-8") as f:
                        f.write(result["xml"])

                    # B. Prozess Trace speichern
                    save_process_trace(filename, result)

                    # C. Datei in Archiv verschieben
                    safe_move_file(file_path, cfg.FOLDERS["ARCHIVE"])
                    logger.info(f"✅ Erfolgreich verarbeitet: {filename} & XML erstellt und gespeichert")

                else:
                    error_msg = str(result['error'])
                    
                    # 1. Check auf AUTH Fehler (401/403) -> SOFORT STOPPEN
                    if "401" in error_msg or "403" in error_msg or "Unauthenticated" in error_msg or "PermissionDenied" in error_msg:
                        logger.critical(f"⛔ KRITISCHER AUTH-FEHLER: {error_msg}")
                        logger.critical("Der Runner wird beendet, um weitere Probleme zu vermeiden. Bitte API-Key/Service Account prüfen.")
                        return # Beendet die main() Funktion und damit das Skript
                    
                    # 2. Check auf RETRY Fehler (429, 500, 503, Timeout) -> WARTEN
                    # 429 = Quota, 5xx = Server Error, Timeout = Verbindung
                    if any(x in error_msg for x in ["429", "RESOURCE_EXHAUSTED", "quota", "500", "503", "InternalServerError", "ServiceUnavailable", "Timeout", "ConnectionError"]):
                        wait_time = cfg.RETRY_WAIT_SECONDS
                        logger.warning(f"⚠️ Temporäres API/Netzwerk-Problem ({error_msg}).") 
                        logger.warning(f"Datei bleibt im Input. Warte {wait_time} Sekunden und versuche es erneut...")
                        time.sleep(wait_time)
                        continue # Nächste Iteration = Retry
                    
                    # 3. Sonstige Fehler (Leeres JSON, Bad Request 400, Parse Error) -> QUARANTÄNE
                    logger.warning(f"❌ Fehler bei der Verarbeitung von {filename}: {error_msg}")

                     # Auch im Fehlerfall Trace Daten speichern (dank Anpassung im Controller sind die da)
                    save_process_trace(filename, result)

                    # Verschieben nach Error Quarantine
                    safe_move_file(file_path, cfg.FOLDERS["ERROR"])

                    # Log schreiben
                    # Wir müssen den Pfad neu berechnen, da safe_move_file evtl umbenannt hat
                    # Aber das Error Log braucht keinen unique name zwingend, oder wir schreiben es in den Trace
                    # Besser: Wir schreiben das Error Log direkt für den Originalnamen in den Error Ordner
                    # Falls die Datei umbenannt wurde, heisst das Textfile halt anders -> akzeptabel.
                    error_destination = os.path.join(cfg.FOLDERS["ERROR"], filename)
                    with open(error_destination + ".txt", "w", encoding="utf-8") as f:
                        f.write(f"Zeitpunkt: {datetime.now()}\nError: {error_msg}\n")


    except KeyboardInterrupt:
        logger.info("Beende Runner ...") # für Strg +C abbruch


if __name__ == "__main__":
    main() # wenn die Datei direkt ausgeführt wird, starte main