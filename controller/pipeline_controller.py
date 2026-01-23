# ersetzt app.py für die Pipeline Steuerung zuvor war es in app.py

import json
import os
import validation
from validation.input_gate import InputGate
from validation.post_processing import enforce_business_rules, generate_xml_from_data
from jinja2 import Environment, FileSystemLoader

class PipelineController:
    
    # Konstruktor Args sind das OCR-Modell und das LLM-Modell für das JSON generierung, Project root ist das XML Template Verzeichnis
    # So bin ich immer flexibel was die Modelle angeht
    def __init__(self, project_root, ocr_engine, llm_engine=None):
        self.project_root = project_root
        self.ocr_engine = ocr_engine
        self.llm_engine = llm_engine
        
        #InputGate initialisieren (für Validierung)
        self.input_gate = InputGate(quarantine_dir="_quarantine")

        ## Template Umgebung für XML laden
        self.env = Environment(loader=FileSystemLoader(os.path.join(project_root, "project_root")))

# Validierung der Datei:
def _validate_file(self, file_bytes, filename, model_name):
    validatioon = self.input_gate.validate(file_bytes=file_bytes, filename=filename, target_model=model_name)

    if not validatioon.is_valid:
        return False, validation.error_message, None
    
    # Hier werden die bereinigten Bytes zurückgegeben (z.B ohne leere Seiten) 
    processed_bytes = validation.processed_bytes or file_bytes
    return True, "", processed_bytes


# OCR Prozess + Direct JSON Generierung
def _run_ocr(self, processed_bytes, filename, pipeline_mode="Classic"):

    # führt OCr durch und unterscheidet nach PDF oder Bild und nach Pipeline Mode
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

    # Ergebnis extrahieren
    # Mistral gibt ein Objekt mit .pages zrück, gemini ein repsonse object

    if hasattr(response, "pages"):
        text_content = ""
        for page in response.pages:
            text_content += page.markdown + "\n\n"
        return text_content, None #Kein JSON Objekt
    
    else: # gemini
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

            # 4. Daten Extraktion (LLM oder Parse)
            json_data = {}
            
            if pipeline_mode == "Direct JSON" and used_schema:
                # Wir haben schon JSON im Text
                json_data = json.loads(extracted_text)
            elif self.llm_engine:
                # Classic Mode: Markdown -> LLM
                # Die extract_and_generate_xml Methode im LLM macht schon Rules + XML,
                # aber wir wollen es hier kontrollieren, also rufen wir nur extraction auf
                # Schau in deine base_llm.py: extract_and_generate_xml macht alles.
                # Nutzen wir das der Einfachheit halber:
                json_data, xml_output = self.llm_engine.extract_and_generate_xml(extracted_text)
                return {
                    "success": True, 
                    "json": json_data, 
                    "xml": xml_output, 
                    "filename": filename
                }
            
            # Falls Direct JSON Mode (hier müssen wir Rules + XML manuell machen)
            if json_data:
                json_data = enforce_business_rules(json_data)
                xml_output = generate_xml_from_data(json_data, self.env)
                return {
                    "success": True, 
                    "json": json_data, 
                    "xml": xml_output, 
                    "filename": filename
                }
            
            return {"success": False, "error": "Keine Daten extrahiert", "filename": filename}

        except Exception as e:
            return {"success": False, "error": str(e), "filename": filename}