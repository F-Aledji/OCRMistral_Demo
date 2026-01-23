import os
import shutil
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Klassen Importieren
from controller.pipeline_controller import PipelineController
from extraction.gemini_ocr_engine import GeminiOCR
from llm.openai_llm import OpenAILLM

#Konfigutation Laden
load_dotenv(override=True)

FOLDERS={
    "INPUT": "01_Input_PDF",
    "OUTPUT": "02_Output_XML",
    "TRACE": "03_Process_Trace",
    "ERROR": "98_Error_Quarantine",
    "ARCHIVE": "99_Archive_Success"
    }

# Logging Setup auf die Konsole

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(message)s')
logger = logging.getLogger("BatchRunner")

def setup_folders():
    """Erstellt alle notwendigen Ordner beim Start."""
    for name, path in FOLDERS.items():
        if not os.path.exists(path):
            os.makedirs(path)
            logger.info(f"Ordner erstellt: {path}")

# Funktion um Daten in 03_process_trace zu speichern + für AI-korrektur
def save_process_trace(filename, result_data):
    try:
        # Dateinamen ohne Endung holen
        base_name = os.path.splitext(filename)[0]

        # Unterordner erstellen im 03_Process_Trace -> beispiel 03_Process_Trace/<filename>/
        trace_dir = os.path.join(FOLDERS["TRACE"], base_name)
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
        with open(os.path.join(trace_dir, "process_log.txt"), "w", encoding="utf-8") as f:
            f.write(f"Processed on: {datetime.now().isoformat()}\n")
            f.write(f"Status: Success\n")
    except Exception as e:
        logger.error(f"Error saving process trace for {filename}: {e}")

def main():
    logger.info("--Starte Batch Verarbeitung--")
    setup_folders() #Ordner erstellen wenn nicht vorhanden
    # Einrichten der Engines
    project_root = os.path.dirname(os.path.abspath(__file__))

    # OCR Engine initialisieren
    if not os.getenv("GEMINI_PROJECT_ID"):
        logger.error("GEMINI_PROJECT_ID nicht zu finden. Die Variable muss in der .env Datei gesetzt sein.")
        return
    
    ocr_engine = GeminiOCR(
        service_account_json_path=os.getenv("GEMINI_APPLICATION_CREDENTIALS"),
        project_id=os.getenv("GEMINI_PROJECT_ID"),
        location=os.getenv("GEMINI_LOCATION", "global")
        )
    
    # 2. LLM Engine initialisieren -> hier OpenAI optional Gemini
    llm_engine =OpenAILLM(project_root) # Alternativ: llm_engine = GeminiLLM(project_root)

    # 3. Controller initialisieren
    controller = PipelineController(project_root, ocr_engine, llm_engine)

    logger.info(f"Überwachung aktiviert für Ordner: {FOLDERS['INPUT']}")
    logger.info("Drücken Sie STRG+C zum Beenden.")

    # --- Main Loop ---
    waiting_message_shown = False
    try:
        while True:
            # Scanne ordner nach PDFs (nicht case-sensitiv)
            files =[f for f in os.listdir(FOLDERS["INPUT"]) if f.lower().endswith(".pdf")]

            if not files: 
                if not waiting_message_shown:
                    logger.info("Keine weiteren Dateien. Warte auf Input...")
                    waiting_message_shown = True
                time.sleep(5)  # Warte 5 Sekunden bevor erneut geprüft wird
                continue
            
            waiting_message_shown = False
            for filename in files:
                file_path = os.path.join(FOLDERS["INPUT"], filename)

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
                    with open(os.path.join(FOLDERS["OUTPUT"], xml_filename), "w", encoding="utf-8") as f:
                        f.write(result["xml"])

                    # B. Prozess Trace speichern
                    save_process_trace(filename, result)

                    # C. Datei in Archiv verschieben
                    shutil.move(file_path, os.path.join(FOLDERS["ARCHIVE"], filename))
                    logger.info(f"✅ Erfolgreich verarbeitet: {filename} & XML erstellt und gespeichert")

                else:
                    # Fehlerbehandlung
                    logger.warning(f"❌ Fehler bei der Verarbeitung von {filename}: {result['error']}")

                    # Verschieben nach Error Quarantine
                    error_destination = os.path.join(FOLDERS["ERROR"], filename)
                    shutil.move(file_path, error_destination)

                    # Log schreiben
                    with open(error_destination + ".txt", "w", encoding="utf-8") as f:
                        f.write(f"Zeitpunkt: {datetime.now()}\nError: {result['error']}\n")


    except KeyboardInterrupt:
        logger.info("Beende Runner ...") # für Strg +C abbruch


if __name__ == "__main__":
    main() # wenn die Datei direkt ausgeführt wird, starte main