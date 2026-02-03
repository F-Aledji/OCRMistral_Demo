import json
import os
import logging
from dataclasses import asdict
from typing import Dict, Any, Optional, Tuple
from pydantic import ValidationError
from schema.models import Document
from validation.input_gate import InputGate
from validation.judge import Judge
from validation.post_processing import generate_xml_from_data
from validation.score import ScoreEngine
from jinja2 import Environment, FileSystemLoader
import config.config as cfg


logger = logging.getLogger(__name__)


class PipelineController:
    
    def __init__(self, project_root, ocr_engine, llm_engine=None):
        """Konstruktor: OCR-Engine, optionales LLM, und Project-Root für Templates."""
        self.project_root = project_root
        self.ocr_engine = ocr_engine
        self.llm_engine = llm_engine
        self.input_gate = InputGate(quarantine_dir=cfg.FOLDERS["ERROR"])
        self.env = Environment(loader=FileSystemLoader(project_root))
        self.ba_number_list = []
        self.ba_number_file = os.path.join(self.project_root, "config", "ba_numbers.txt")
        self.judge = Judge()  # Judge für Reparaturversuche
        self.score_engine = ScoreEngine()  # ScoreEngine für Bewertung
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def get_validation_context(self) -> Dict[str, Any]:
        """Lädt die erlaubten BA-Nummern aus Datei oder Liste."""
        valid_bas = []
        if os.path.exists(self.ba_number_file):
            try:
                with open(self.ba_number_file, "r", encoding="utf-8") as f:
                    valid_bas = [line.strip() for line in f if line.strip()]
            except Exception as e:
                logger.error(f"BA-Liste konnte nicht geladen werden: {e}")
        if not valid_bas: 
            valid_bas = self.ba_number_list
        return {"valid_ba_list": valid_bas}

    def _validate_file(self, file_bytes: bytes, filename: str, model_name: str) -> Tuple[bool, str, Optional[bytes]]:
        """Validiert die Eingabedatei über InputGate."""
        result = self.input_gate.validate(file_bytes=file_bytes, filename=filename, target_model=model_name)
        if not result.is_valid:
            return False, result.error_message, None
        return True, "", result.processed_bytes or file_bytes

    def _run_ocr(self, processed_bytes: bytes, filename: str, pipeline_mode: str = "Classic") -> Tuple[str, Optional[Dict]]:
        """Führt OCR durch und gibt extrahierten Text + Schema zurück."""
        is_pdf = filename.lower().endswith(".pdf")
        ocr_json_schema = None

        if pipeline_mode == "Direct JSON" and "Gemini" in self.ocr_engine.__class__.__name__:
            schema_path = os.path.join(self.project_root, "schema", "schema.json")
            with open(schema_path, "r", encoding="utf-8") as f:
                ocr_json_schema = json.load(f)

        if is_pdf:
            response = self.ocr_engine.process_pdf(processed_bytes, stream=False, json_schema=ocr_json_schema)
        else:
            response = self.ocr_engine.process_image(processed_bytes, json_schema=ocr_json_schema)

        return response.text, ocr_json_schema

    def _extract_json_data(self, extracted_text: str, pipeline_mode: str, used_schema: Optional[Dict], filename: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Extrahiert JSON-Daten aus OCR-Text oder via LLM."""
        if pipeline_mode == "Direct JSON" and used_schema:
            try:
                return json.loads(extracted_text), None
            except json.JSONDecodeError as e:
                return None, f"Modell lieferte ungültiges JSON: {e}"
        elif self.llm_engine:
            raw_json_data, _ = self.llm_engine.extract_and_generate_xml(extracted_text)
            return raw_json_data, None
        return None, "Kein Extraktionsmodus verfügbar"

    def _format_validation_errors(self, ve: ValidationError) -> Tuple[str, list]:
        """Formatiert Pydantic ValidationErrors für Logging und Judge."""
        error_list = []
        error_messages = []
        for err in ve.errors():
            loc = "->".join(str(x) for x in err.get('loc', []))
            msg = err.get('msg', 'Unbekannter Fehler')
            error_messages.append(f"Feld {loc}: {msg}")
            error_list.append({"field": loc, "message": msg})
        return " | ".join(error_messages), error_list

    def _try_validate_with_repair(
        self, 
        raw_json: Dict, 
        file_bytes: bytes, 
        filename: str, 
        context: Dict,
        max_retries: int = 1
    ) -> Tuple[Optional[Document], Optional[str], Optional[Dict]]:
        """
        Validiert JSON-Daten mit optionalem Judge-Reparaturversuch.
        Returns: (validated_doc, error_message, final_raw_json)
        """
        current_json = raw_json
        
        for attempt in range(max_retries + 1):
            try:
                validated_doc = Document.model_validate(current_json, context=context)
                if attempt > 0:
                    logger.info(f"Judge-Reparatur erfolgreich für {filename} (Versuch {attempt})")
                return validated_doc, None, current_json
            
            except ValidationError as ve:
                error_msg, error_list = self._format_validation_errors(ve)
                logger.warning(f"Validierungsfehler für {filename} (Versuch {attempt + 1}): {error_msg}")
                
                # Bei letztem Versuch: Fehler zurückgeben
                if attempt >= max_retries:
                    return None, error_msg, current_json
                
                # Judge-Reparatur versuchen
                logger.info(f"Starte Judge-Reparatur für {filename}...")
                healed_json = self.judge.heal_json(file_bytes, filename, current_json, error_list)
                
                if not healed_json:
                    logger.warning(f"Judge konnte {filename} nicht reparieren")
                    return None, error_msg, current_json
                
                current_json = healed_json
        
        return None, "Maximale Reparaturversuche erreicht", current_json

    def _build_result(self, success: bool, filename: str, **kwargs) -> Dict[str, Any]:
        """Erstellt ein standardisiertes Ergebnis-Dictionary."""
        result = {"success": success, "filename": filename}
        result.update(kwargs)
        return result

    # =========================================================================
    # MAIN PROCESSING METHOD
    # =========================================================================

    def process_document(self, file_path: str, pipeline_mode: str = "Classic") -> Dict[str, Any]:
        """Hauptfunktion: Steuert den gesamten Verarbeitungsablauf für eine Datei."""
        filename = os.path.basename(file_path)
        
        # 1. Datei lesen
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        # 2. Input-Validierung
        is_valid, error_msg, processed_bytes = self._validate_file(file_bytes, filename, "Gemini OCR")
        if not is_valid:
            return self._build_result(False, filename, error=error_msg)

        try:
            # 3. OCR ausführen
            extracted_text, used_schema = self._run_ocr(processed_bytes, filename, pipeline_mode)
            if not extracted_text or not extracted_text.strip():
                return self._build_result(False, filename, error="OCR: Extrahierter Text ist leer")

            # 4. JSON-Daten extrahieren
            raw_json_data, extract_error = self._extract_json_data(extracted_text, pipeline_mode, used_schema, filename)
            if extract_error:
                return self._build_result(False, filename, error=extract_error)
            if not raw_json_data:
                return self._build_result(False, filename, error="Keine Daten extrahiert")

            # 5. Pydantic-Validierung mit Judge-Reparatur
            validation_context = self.get_validation_context()
            validated_doc, val_error, final_json = self._try_validate_with_repair(
                raw_json_data, file_bytes, filename, validation_context
            )
            
            if val_error:
                return self._build_result(False, filename, error=f"Validierungsfehler: {val_error}", raw_json=final_json)

            # 6. XML generieren
            clean_json_data = validated_doc.model_dump(by_alias=True, mode="json")
            xml_generated = generate_xml_from_data(clean_json_data, self.env)

            # 7. Scoring
            scorer = ScoreEngine()
            score_cards = [] # Die Bewertungs_Ergebniss werden hier gesammelt beispiel {"total_score": 85, "penalties": [...], "signals": [...]}
            for doc in validated_doc.documents:
                score_card = scorer.evaluate(doc.supplierConfirmation)
                score_cards.append(asdict(score_card))

            return self._build_result(
                True,
                filename,
                json=clean_json_data,
                xml=xml_generated,
                score_cards=score_cards,
            )

        except Exception as e:
            logger.exception(f"Unerwarteter Fehler bei {filename}")
            return self._build_result(False, filename, error=str(e))