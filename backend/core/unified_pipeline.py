# =============================================================================
# UNIFIED PIPELINE
# =============================================================================
# Zentrale Pipeline-Klasse für Dokumentenverarbeitung.
# Wird sowohl vom Backend (API) als auch vom Batch-Runner genutzt.
#
# Basiert auf dem bewährten Aufbau des batch_runner.py:
# 1. Input-Validierung
# 2. OCR-Extraktion
# 3. JSON-Parsing
# 4. Pydantic-Validierung
# 5. Optional: Judge-Reparatur
# 6. Scoring
# 7. Optional: XML-Generierung
# =============================================================================

import os
import json
import logging
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List, Tuple
import io
import re
try:
    import pypdf
except ImportError:
    pypdf = None

# Pipeline-Komponenten
from pydantic import ValidationError
from jinja2 import Environment, FileSystemLoader
from sqlmodel import Session, select

# Support both: running from project root (backend.X) and from backend dir (X)
try:
    from backend.schema.ocr_schema import Document
    from backend.config import config as cfg
    from backend.validation.input_gate import InputGate
    from backend.validation.score import ScoreEngine
    from backend.validation.judge import Judge
except ImportError:
    from schema.ocr_schema import Document
    from config import config as cfg
    from validation.input_gate import InputGate
    from validation.score import ScoreEngine
    from validation.judge import Judge

# Backend Root ermitteln (für Jinja2 Templates)
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_ROOT)

logger = logging.getLogger(__name__)

# DB-Abhängigkeiten optional laden
try:
    from backend.app.db import engine
    from backend.app.db_models import ValidBANumber, SupplierTemplate
    from backend.app.services.prescan import get_prescan_service
    DB_AVAILABLE = True
except ImportError:
    try:
        from app.db import engine
        from app.db_models import ValidBANumber, SupplierTemplate
        from app.services.prescan import get_prescan_service
        DB_AVAILABLE = True
    except ImportError:
        logger.warning("DB/Service Import fehlgeschlagen in UnifiedPipeline - Hybrid Logik deaktiviert")
        DB_AVAILABLE = False


# =============================================================================
# RESULT DATACLASS
# =============================================================================

@dataclass
class PipelineResult:
    """Ergebnis der Pipeline-Verarbeitung."""
    success: bool
    filename: str
    error: Optional[str] = None
    
    # Daten-Felder
    raw_json: Optional[Dict[str, Any]] = None
    validated_json: Optional[Dict[str, Any]] = None
    xml: Optional[str] = None
    
    # Metadaten / Metriken
    file_size_bytes: int = 0
    page_count: int = 0
    is_scanned: bool = False
    
    # Scoring
    score_cards: List[Dict[str, Any]] = field(default_factory=list)
    avg_score: int = 0
    initial_score: int = 0  # Score VOR Business Repair
    
    # Metadaten
    pipeline_mode: str = "Direct JSON"
    judge_repaired: bool = False  # Wurde überhaupt repariert? (Schema ODER Business)
    schema_repair_attempted: bool = False  # Schema-Repair versucht?
    business_repair_attempted: bool = False  # Business-Repair versucht?
    business_repair_success: bool = False  # Business-Repair erfolgreich?
    
    # Eskalations-Flag: True wenn Validierung fehlschlug UND Judge nicht helfen konnte
    # → Dokument muss manuell geprüft werden
    needs_manual_review: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert zu Dictionary für JSON-Serialisierung."""
        return {
            "success": self.success,
            "filename": self.filename,
            "error": self.error,
            "json": self.validated_json,
            "xml": self.xml,
            "score_cards": self.score_cards,
            "avg_score": self.avg_score,
            "pipeline_mode": self.pipeline_mode,
            "judge_repaired": self.judge_repaired,
            "needs_manual_review": self.needs_manual_review,
            # Metriken
            "file_size_bytes": self.file_size_bytes,
            "page_count": self.page_count,
            "is_scanned": self.is_scanned
        }


# =============================================================================
# UNIFIED PIPELINE
# =============================================================================

class UnifiedPipeline:
    """
    Zentrale Pipeline für Dokumentenverarbeitung.
    
    Beispiel:
        pipeline = UnifiedPipeline()
        result = pipeline.process_bytes(pdf_bytes, "rechnung.pdf")
        
        if result.success:
            print(f"Score: {result.avg_score}")
        else:
            print(f"Fehler: {result.error}")
    """
    
    def __init__(
        self, 
        ocr_engine=None,
        enable_judge: bool = True,
        enable_xml: bool = True,
        quarantine_dir: Optional[str] = None
    ):
        """
        Initialisiert die Pipeline.
        
        Args:
            ocr_engine: Eine OCR-Engine (GeminiOCR, MistralOCR). Falls None, wird Gemini genutzt.
            enable_judge: Aktiviert Judge-Reparatur bei Validierungsfehlern
            enable_xml: Generiert XML-Output
            quarantine_dir: Ordner für abgelehnte Dateien
        """
        self.ocr_engine = ocr_engine
        self.enable_judge = enable_judge
        self.enable_xml = enable_xml
        
        # Komponenten initialisieren
        self.input_gate = InputGate(
            quarantine_dir=quarantine_dir or cfg.FOLDERS.get("ERROR")
        )
        self.score_engine = ScoreEngine()
        self.judge = Judge() if enable_judge else None
        self.env = Environment(loader=FileSystemLoader(PROJECT_ROOT))
        
        # Pre-Scan Service
        self.prescan = get_prescan_service() if DB_AVAILABLE else None
        
        # BA-Nummern für Validierung
        self.ba_numbers_file = os.path.join(PROJECT_ROOT, "config", "ba_numbers.txt")
        
        # OCR-Engine lazy initialisieren falls nicht übergeben
        if self.ocr_engine is None:
            self._init_default_ocr()
    
    def _init_default_ocr(self):
        """Initialisiert die Standard-OCR-Engine (Gemini)."""
        try:
            try:
                from backend.extraction.gemini_ocr_engine import GeminiOCR
            except ImportError:
                from extraction.gemini_ocr_engine import GeminiOCR
                
            if cfg.GEMINI_PROJECT_ID:
                self.ocr_engine = GeminiOCR(
                    service_account_json_path=cfg.GEMINI_CREDENTIALS,
                    project_id=cfg.GEMINI_PROJECT_ID,
                    location=cfg.GEMINI_LOCATION
                )
                logger.info("OCR-Engine (Gemini) initialisiert")
            else:
                logger.warning("GEMINI_PROJECT_ID nicht gesetzt")
        except Exception as e:
            logger.error(f"OCR-Engine Fehler: {e}")

    def _check_db_supplier(self, ba_number: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Prüft ob BA-Nummer in DB existiert und ob ein Template vorhanden ist.
        Returns: (known_supplier, template_coords)
        """
        if not DB_AVAILABLE or not ba_number:
            return False, None
            
        try:
            # sa_session verwenden wir nicht direkt da wir nicht in FastAPI Context sind
            # Wir erstellen kurzlebige Session für den Lookup
            with Session(engine) as session:
                # 1. BA Nummer suchen
                statement = select(ValidBANumber).where(ValidBANumber.ba_number == ba_number)
                result = session.exec(statement).first()
                
                if not result:
                    return False, None
                
                # Wenn gefunden:
                supplier_id = result.supplier_id
                
                # 2. Template suchen
                tmpl_statement = select(SupplierTemplate).where(SupplierTemplate.supplier_id == supplier_id)
                tmpl_result = session.exec(tmpl_statement).first()
                
                coords = tmpl_result.coordinates_json if tmpl_result else None
                
                logger.info(f"DB Match: BA={ba_number} -> Supplier={result.supplier_name} (Template Found={coords is not None})")
                return True, coords
                
        except Exception as e:
            logger.error(f"DB Lookup Fehler: {e}")
            return False, None
            
    def _analyze_pdf(self, file_bytes: bytes) -> Tuple[int, bool]:
        """
        Analysiert PDF auf Metriken.
        Returns: (page_count, is_scanned)
        """
        if not pypdf:
            return 0, False
            
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            page_count = len(reader.pages)
            
            # Scanned Check: Prüfe Text auf den ersten 3 Seiten
            text_len = 0
            check_pages = min(3, page_count)
            for i in range(check_pages):
                try:
                    text_len += len(reader.pages[i].extract_text() or "")
                except:
                    pass
            
            # Wenn sehr wenig Text extrahierbar ist -> Vermutlich gescannt
            # Threshold: 20 Zeichen pro Seite im Schnitt
            is_scanned = (text_len / check_pages) < 20 if check_pages > 0 else False
            
            return page_count, is_scanned
        except Exception as e:
            logger.warning(f"PDF Analyse Fehler: {e}")
            return 0, False
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _load_ba_numbers(self) -> List[str]:
        """Lädt erlaubte BA-Nummern aus Datei."""
        if os.path.exists(self.ba_numbers_file):
            try:
                with open(self.ba_numbers_file, "r", encoding="utf-8") as f:
                    return [line.strip() for line in f if line.strip()]
            except Exception as e:
                logger.error(f"BA-Liste Fehler: {e}")
        return []
    
    def _load_json_schema(self) -> Optional[Dict]:
        """Lädt das JSON-Schema für Gemini Structured Output."""
        schema_path = os.path.join(PROJECT_ROOT, "schema", "schema.json")
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Schema-Fehler: {e}")
            return None
    
    def _format_validation_errors(self, ve: ValidationError) -> Tuple[str, List[Dict]]:
        """Formatiert Pydantic-Fehler für Logging und Judge."""
        error_list = []
        messages = []
        for err in ve.errors():
            loc = "->".join(str(x) for x in err.get('loc', []))
            msg = err.get('msg', 'Unbekannter Fehler')
            messages.append(f"Feld {loc}: {msg}")
            error_list.append({"field": loc, "message": msg})
        return " | ".join(messages), error_list
    
    def _try_validate_with_repair(
        self,
        raw_json: Dict,
        file_bytes: bytes,
        filename: str,
        context: Dict
    ) -> Tuple[Optional[Document], Optional[str], Optional[Dict], bool]:
        """
        Validiert JSON mit optionalem Judge-Reparaturversuch.
        
        Returns:
            (validated_doc, error_message, final_json, was_repaired)
        """
        current_json = raw_json
        was_repaired = False
        
        # Erster Versuch
        try:
            validated = Document.model_validate(current_json, context=context)
            return validated, None, current_json, False
        except ValidationError as ve:
            error_msg, error_list = self._format_validation_errors(ve)
            logger.warning(f"Validierungsfehler für {filename}: {error_msg}")
            
            # Judge-Reparatur versuchen
            if self.judge and self.enable_judge:
                # Hybrid Logic: Versuche Template für Judge zu finden
                template_coords = None
                try:
                    cand_ba = current_json.get("supplierConfirmation", {}).get("Correspondence", {}).get("number")
                    # Fallback Struktur
                    if not cand_ba:
                         cand_ba = current_json.get("Correspondence", {}).get("number")
                    
                    if cand_ba:
                        _, template_coords = self._check_db_supplier(cand_ba)
                        if template_coords:
                             logger.info(f"Template-Koordinaten für Judge gefunden ({filename})")
                except Exception:
                    pass

                logger.info(f"Starte Judge-Reparatur für {filename}...")
                healed = self.judge.heal_json(file_bytes, filename, current_json, error_list, template_coords=template_coords)
                
                if healed:
                    try:
                        validated = Document.model_validate(healed, context=context)
                        logger.info(f"Judge-Reparatur erfolgreich für {filename}")
                        return validated, None, healed, True
                    except ValidationError as ve2:
                        error_msg, _ = self._format_validation_errors(ve2)
            
            return None, error_msg, current_json, False
    
    # =========================================================================
    # MAIN PROCESSING
    # =========================================================================
    
    def process_bytes(
        self, 
        file_bytes: bytes, 
        filename: str,
        pipeline_mode: str = "Direct JSON"
    ) -> PipelineResult:
        """
        Verarbeitet eine Datei (PDF oder Bild) durch die Pipeline.
        
        Args:
            file_bytes: Datei als Bytes
            filename: Dateiname
            pipeline_mode: "Direct JSON" (Gemini mit Schema) oder "Classic" (OCR + LLM)
        
        Returns:
            PipelineResult mit allen Ergebnissen
        """
        # OCR-Engine prüfen
        if not self.ocr_engine:
            return PipelineResult(
                success=False,
                filename=filename,
                error="OCR-Engine nicht verfügbar"
            )
        
        # 1. Input-Validierung
        validation = self.input_gate.validate(file_bytes, filename, "Gemini OCR")
        if not validation.is_valid:
            return PipelineResult(
                success=False,
                filename=filename,
                error=validation.error_message
            )
        processed_bytes = validation.processed_bytes or file_bytes
        
        # Metriken berechnen
        file_size_bytes = len(file_bytes)
        page_count, is_scanned = 0, False
        if filename.lower().endswith(".pdf"):
            page_count, is_scanned = self._analyze_pdf(file_bytes)
        
        # Fast-Pass: Template suchen BEVOR wir die teure OCR starten
        pre_hints = None
        try:
            if self.prescan:
                fast_ba = self.prescan.scan_for_ba_number(file_bytes, filename)
                if fast_ba:
                    _, tmpl_coords = self._check_db_supplier(fast_ba)
                    if tmpl_coords:
                         logger.info(f"Fast-Pass: Template gefunden für BA {fast_ba}")
                         pre_hints = tmpl_coords
        except Exception as e:
            logger.warning(f"Fast-Pass Fehler: {e}")

        try:
            # 2. OCR mit JSON-Schema ausführen
            json_schema = self._load_json_schema() if pipeline_mode == "Direct JSON" else None
            
            is_pdf = filename.lower().endswith(".pdf")
            if is_pdf:
                response = self.ocr_engine.process_pdf(processed_bytes, stream=False, json_schema=json_schema, hints=pre_hints)
            else:
                response = self.ocr_engine.process_image(processed_bytes, json_schema=json_schema, hints=pre_hints)
            
            extracted_text = response.text
            if not extracted_text or not extracted_text.strip():
                return PipelineResult(
                    success=False,
                    filename=filename,
                    error="OCR lieferte leeren Text"
                )
            
            # 3. JSON parsen
            try:
                raw_json = json.loads(extracted_text)
            except json.JSONDecodeError as e:
                return PipelineResult(
                    success=False,
                    filename=filename,
                    error=f"Ungültiges JSON: {e}"
                )
            
            # 4. Pydantic-Validierung (mit Judge-Reparatur)
            context = {"valid_ba_list": self._load_ba_numbers()}
            validated_doc, val_error, final_json, was_repaired = self._try_validate_with_repair(
                raw_json, file_bytes, filename, context
            )
            
            # =========================================================================
            # ESKALATIONS-LOGIK (NEU)
            # =========================================================================
            # Bei Validierungsfehler nach Judge-Failure:
            # → NICHT abbrechen, sondern zur manuellen Prüfung eskalieren
            # → success=True damit trace_service das Dokument ins Frontend pusht
            
            # =========================================================================
            # TRACKING VARIABLEN für Datenbank-KPIs
            # =========================================================================
            schema_repair_attempted = was_repaired  # Wurde Schema-Reparatur versucht?
            business_repair_attempted = False       # Wird Business-Reparatur versucht?
            business_repair_success = False         # War Business-Reparatur erfolgreich?
            initial_score = 0                       # Score vor Business-Reparatur
            
            needs_manual_review = False
            if val_error:
                logger.warning(f"Eskalation zur manuellen Prüfung: {filename} - {val_error}")
                needs_manual_review = True
                # Nutze das (ungültige) JSON trotzdem für die Anzeige im Frontend
                validated_json = final_json
                score_cards = []
                avg_score = 0
            else:
                # 5. JSON serialisieren (nur wenn Validierung erfolgreich)
                validated_json = validated_doc.model_dump(by_alias=True, mode="json")
                
                # 6. Scoring (ERSTE RUNDE)
                score_cards = []
                for doc in validated_doc.documents:
                    # Hybrid Logic: DB Check vor Scoring
                    sc = doc.supplierConfirmation
                    ba_number = None
                    if sc.Correspondence:
                        ba_number = sc.Correspondence.number
                    
                    # Check gegen DB (wenn verfügbar)
                    known_supplier, template_coords = self._check_db_supplier(ba_number)
                    template_match = template_coords is not None
                    
                    card = self.score_engine.evaluate(
                        sc, 
                        known_supplier=known_supplier, 
                        template_match=template_match
                    )
                    score_cards.append(asdict(card))
                
                avg_score = sum(c["total_score"] for c in score_cards) // len(score_cards) if score_cards else 0
                initial_score = avg_score  # Score vor Business-Reparatur speichern
                
                # =====================================================================
                # BUSINESS REPAIR LOOP (NEU!)
                # =====================================================================
                # Wenn Score < 85 UND Judge verfügbar:
                # → Versuche Business-Reparatur basierend auf Score-Penalties
                
                if avg_score < 85 and self.judge and self.enable_judge:
                    logger.info(f"Score {avg_score} < 85 für {filename} → Starte Business Repair...")
                    business_repair_attempted = True
                    
                    # Sammle alle Penalties aus den ScoreCards
                    business_errors = []
                    for idx, card in enumerate(score_cards):
                        for penalty in card.get("penalties", []):
                            business_errors.append({
                                "field": f"document_{idx}",
                                "message": penalty
                            })
                    
                    if business_errors:
                        # Template-Koordinaten für Judge holen (falls verfügbar)
                        try:
                            first_doc = validated_doc.documents[0] if validated_doc.documents else None
                            ba_num = None
                            if first_doc and first_doc.supplierConfirmation.Correspondence:
                                ba_num = first_doc.supplierConfirmation.Correspondence.number
                            
                            _, template_coords = self._check_db_supplier(ba_num) if ba_num else (False, None)
                        except:
                            template_coords = None
                        
                        # Judge aufrufen mit Business-Fehlern
                        logger.info(f"Business Repair: {len(business_errors)} Probleme gefunden")
                        repaired_json = self.judge.heal_json(
                            file_bytes, 
                            filename, 
                            validated_json,  # Aktuelles (valides!) JSON
                            business_errors, 
                            template_coords=template_coords
                        )
                        
                        if repaired_json:
                            # Erneute Validierung + Scoring
                            try:
                                validated_doc_v2 = Document.model_validate(repaired_json, context=context)
                                validated_json = validated_doc_v2.model_dump(by_alias=True, mode="json")
                                
                                # Scoring ZWEITE RUNDE
                                score_cards = []
                                for doc in validated_doc_v2.documents:
                                    sc = doc.supplierConfirmation
                                    ba_number = None
                                    if sc.Correspondence:
                                        ba_number = sc.Correspondence.number
                                    
                                    known_supplier, template_coords = self._check_db_supplier(ba_number)
                                    template_match = template_coords is not None
                                    
                                    card = self.score_engine.evaluate(
                                        sc, 
                                        known_supplier=known_supplier, 
                                        template_match=template_match
                                    )
                                    score_cards.append(asdict(card))
                                
                                new_score = sum(c["total_score"] for c in score_cards) // len(score_cards) if score_cards else 0
                                
                                if new_score > avg_score:
                                    logger.info(f"✓ Business Repair erfolgreich: Score {avg_score} → {new_score}")
                                    avg_score = new_score
                                    business_repair_success = True
                                    was_repaired = True  # Gesamtstatus: Repariert
                                else:
                                    logger.info(f"Business Repair keine Verbesserung: {avg_score} → {new_score}")
                            
                            except ValidationError as ve:
                                logger.warning(f"Business Repair führte zu Validierungsfehler: {ve}")
                    else:
                        logger.info("Keine konkreten Penalties für Business Repair gefunden")
            
            # 7. XML generieren (nur wenn Validierung erfolgreich)
            xml_output = None
            if self.enable_xml and not needs_manual_review:
                xml_output = generate_xml_from_data(validated_json, self.env)
            
            return PipelineResult(
                success=True,  # Immer True - auch bei Eskalation!
                filename=filename,
                error=val_error,  # Fehlermeldung für Anzeige im Frontend
                raw_json=raw_json,
                validated_json=validated_json,
                xml=xml_output,
                score_cards=score_cards,
                avg_score=avg_score,
                initial_score=initial_score,
                pipeline_mode=pipeline_mode,
                judge_repaired=was_repaired,
                schema_repair_attempted=schema_repair_attempted,
                business_repair_attempted=business_repair_attempted,
                business_repair_success=business_repair_success,
                needs_manual_review=needs_manual_review,
                file_size_bytes=file_size_bytes,
                page_count=page_count,
                is_scanned=is_scanned
            )
            
        except Exception as e:
            logger.exception(f"Pipeline-Fehler für {filename}")
            return PipelineResult(
                success=False,
                filename=filename,
                error=str(e)
            )
    
    def process_file(self, file_path: str, pipeline_mode: str = "Direct JSON") -> PipelineResult:
        """
        Verarbeitet eine Datei vom Dateisystem.
        
        Args:
            file_path: Pfad zur Datei
            pipeline_mode: Pipeline-Modus
        
        Returns:
            PipelineResult
        """
        filename = os.path.basename(file_path)
        
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            return self.process_bytes(file_bytes, filename, pipeline_mode)
        except FileNotFoundError:
            return PipelineResult(
                success=False,
                filename=filename,
                error=f"Datei nicht gefunden: {file_path}"
            )
        except Exception as e:
            return PipelineResult(
                success=False,
                filename=filename,
                error=f"Fehler beim Lesen: {e}"
            )


# =============================================================================
# XML GENERATION HELPER
# =============================================================================

def generate_xml_from_data(data: Dict[str, Any], env: Environment) -> Optional[str]:
    """Generiert XML aus validiertem JSON (Placeholder)."""
    # TODO: XML-Template laden und rendern
    return None


# =============================================================================
# SINGLETON
# =============================================================================

_pipeline_instance: Optional[UnifiedPipeline] = None

def get_pipeline() -> UnifiedPipeline:
    """Gibt die Pipeline-Singleton-Instanz zurück."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = UnifiedPipeline()
    return _pipeline_instance
