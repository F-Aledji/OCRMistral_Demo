# ersetzt app.py für die Pipeline Steuerung zuvor war es in app.py
import json
import os
import logging
from pydantic import ValidationError
from schema.models import Document
from validation.input_gate import InputGate
from validation.post_processing import generate_xml_from_data
from jinja2 import Environment, FileSystemLoader
import config.config as cfg

logger = logging.getLogger(__name__)

class PipelineController:
    
    # Konstruktor Args sind das OCR-Modell und das LLM-Modell für das JSON generierung, Project root ist das XML Template Verzeichnis
    # So bin ich immer flexibel was die Modelle angeht
    def __init__(self, project_root, ocr_engine, llm_engine=None):
        self.project_root = project_root
        self.ocr_engine = ocr_engine
        self.llm_engine = llm_engine
        # InputGate initialisieren - nutzt ERROR Ordner für Quarantäne
        self.input_gate = InputGate(quarantine_dir=cfg.FOLDERS["ERROR"])
        ## Template Umgebung für XML laden
        self.env = Environment(loader=FileSystemLoader(project_root))
        self.ba_number_list = []
        self.ba_number_file = os.path.join(self.project_root, "config", "ba_numbers.txt") # kann auch anders lauten
    
    def get_validation_context(self):
        """Lädt die eraubten BA-Nummern aus der Datei. Prio auf Datei statt Liste"""
        valid_bas = []

        # Versuch aus Datei zu laden
        if os.path.exists(self.ba_number_file):
            try:
                with open(self.ba_number_file, "r", encoding="utf-8") as f:
                    # Zeile für zeile, leerzeichen weg, leere zeilen ignorieren
                    valid_bas = [line.strip() for line in f if line.strip()]
            except Exception as e:
                logger.error(f"BA-Liste konnte nicht geladen werden {e}")

        # Versuch aus der Liste zu laden
        if not valid_bas: 
            valid_bas = self.ba_number_list

        return {"valid_ba_list": valid_bas}


    # Validierung der Datei:
    def _validate_file(self, file_bytes, filename, model_name):
        validation_result = self.input_gate.validate(file_bytes=file_bytes, filename=filename, target_model=model_name)
        if not validation_result.is_valid:
            return False, validation_result.error_message, None
        
        # Hier werden die bereinigten Bytes zurückgegeben (z.B ohne leere Seiten) 
        processed_bytes = validation_result.processed_bytes or file_bytes
        return True, "", processed_bytes


    # OCR Prozess + Direct JSON Generierung
    def _run_ocr(self, processed_bytes, filename, pipeline_mode="Classic"):
        # führt OCR durch und unterscheidet nach PDF oder Bild und nach Pipeline Mode
        is_pdf = filename.lower().endswith(".pdf")
        ocr_json_schema = None

        # Schema laden für Direct JSON Mode (nur gemini)
        if pipeline_mode == "Direct JSON" and "Gemini" in self.ocr_engine.__class__.__name__:
            schema_path = os.path.join(self.project_root, "schema", "schema.json")
            with open(schema_path, "r", encoding="utf-8") as f:
                ocr_json_schema = json.load(f)


        # Unterscheidung PDF vs Bild
        if is_pdf:
            # bei "Direct JSON" Modus direkt an die OCR Engine
            response = self.ocr_engine.process_pdf(processed_bytes,stream=False, json_schema=ocr_json_schema)

        else:
            response = self.ocr_engine.process_image(processed_bytes, json_schema=ocr_json_schema)

        return response.text, ocr_json_schema
        


    def process_document(self, file_path, pipeline_mode="Classic"):
            #Hauptfunktion: Steuert den gesamten Ablauf für eine Datei.
            filename = os.path.basename(file_path)
            
            # 1. Datei lesen
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            # 2. Validieren
            # Wir nehmen hier einfach "Gemini OCR" als Standard für Limits an, oder du übergibst es
            is_valid, error_msg, processed_bytes = self._validate_file(file_bytes, filename, "Gemini OCR")
            if not is_valid:
                return {"success": False, "error": error_msg, "filename": filename}

            try:
                # 3. OCR Ausführen
                extracted_text, used_schema = self._run_ocr(processed_bytes, filename, pipeline_mode)

                if not extracted_text or not extracted_text.strip():
                     return {
                        "success": False, 
                        "error": "OCR Warning: Extrahierter Text ist leer.", 
                        "filename": filename
                    }

                # 4. Daten Extraktion (LLM oder Parse)
                raw_json_data = {}
                
                if pipeline_mode == "Direct JSON" and used_schema:
                    try:
                    # Wir haben schon JSON im Text
                        raw_json_data = json.loads(extracted_text)
                    except json.JSONDecodeError as e:
                        return {
                            "success": False,
                            "error": f"Modell lieferte ungültiges JSON: {e}",
                            "filename": filename
                        }
                    
                elif self.llm_engine:
                    # Code für Classic Mode: Markdown -> LLM
                    # 
                    raw_json_data, xml_output = self.llm_engine.extract_and_generate_xml(extracted_text)
                    
                if not raw_json_data:
                    return {"success": False, "error": "Keine Daten extrahiert", "filename": filename}
                # Falls Direct JSON Mode (hier müssen wir Rules + XML manuell machen)

                # -- Pydantic Validierung und Logik
                try: 
                    # A Kontext laden (BA Nummern)
                    validation_context = self.get_validation_context()

                    # B. Validierung  & Cleaning starten: Float, Datum, BA Nummern prüfen
                    validated_doc = Document.model_validate(raw_json_data, context=validation_context)

                    # C. Saubere Daten exportieren
                    clean_json_data = validated_doc.model_dump(by_alias=True, mode="json") # modeldump erstell ein dict 
                    
                    # D. XML Generierung (mit sauberen Daten)
                    xml_generated = generate_xml_from_data(clean_json_data, self.env)

                    return{
                        "success": True,
                        "json": clean_json_data,
                        "xml": xml_generated,
                        "filename": filename
                     }
                except ValidationError as ve:
                    # --- hier komt der Judge --- aktuell nur ein Abbruch mit Fehler
                    logger.error(f"Validierungsfehler für {filename}: {ve}")
                    error_messages = []
                    for i in ve.errors():
                        location = "->".join(str(x) for x in i['location'])
                        message = i['message']
                        error_messages.append(f"Feld {location}: {message}")

                    full_error_message = " | ".join(error_messages)

                    return {
                        "success": False,
                        "error": f"Validierungsfehler: {full_error_message}",
                        "filename": filename,
                        "raw_json": raw_json_data # zum Debuggen wegen fehler
                    }

            except Exception as e:
                return {"success": False, "error": str(e), "filename": filename}