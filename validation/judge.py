# =============================================================================
# JUDGE - KI-gestützte JSON-Reparatur
# =============================================================================
#
# ZWECK:
# Wenn die OCR-Extraktion fehlerhafte JSON-Daten liefert (z.B. ungültiges Format,
# fehlende Pflichtfelder), versucht der "Judge" diese automatisch zu reparieren.
#
# ABLAUF:
# 1. OCR liefert fehlerhaftes JSON → Pydantic-Validierung schlägt fehl
# 2. Judge erhält: Originaldokument (PDF/Bild) + fehlerhaftes JSON + Fehlerliste
# 3. Judge sendet alles an ein LLM (Gemini/OpenAI) mit Reparatur-Prompt
# 4. LLM analysiert das Originaldokument erneut und liefert korrigiertes JSON
#
# KONFIGURATION:
# - JUDGE_PROVIDER: "Google" oder "OpenAI" (in config/config.py)
# - JUDGE_MODEL: z.B. "gemini-2.0-flash" (in config/config.py)
#
# WICHTIG:
# Der Judge ist ein "zweiter Versuch" - er ist langsamer und teurer als die
# normale Extraktion, wird aber nur bei Fehlern aktiviert.
#
# =============================================================================

import json
import logging
import os
import base64
from typing import List, Dict, Any, Optional
import config.config as cfg
from utils.prompt_loader import load_prompt
from utils.schema_utils import clean_json_schema

# -----------------------------------------------------------------------------
# PROVIDER-VERFÜGBARKEIT PRÜFEN
# -----------------------------------------------------------------------------
# Die SDKs werden optional importiert - nicht jeder hat beide installiert

try:
    from google import genai
    from google.genai import types
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

try: 
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# JUDGE KLASSE
# =============================================================================

class Judge:
    """
    Repariert fehlerhafte JSON-Extraktion durch erneute KI-Analyse.
    
    Der Judge erhält sowohl das Originaldokument als auch die Fehlerliste
    und kann so gezielt die problematischen Felder korrigieren.
    
    Beispiel:
        judge = Judge()
        repaired = judge.heal_json(
            file_bytes=pdf_content,
            filename="rechnung.pdf",
            broken_json={"date": "invalid"},
            error_list=[{"field": "date", "message": "Ungültiges Datumsformat"}]
        )
    """
    
    def __init__(self):
        # Provider und Modell aus Konfiguration laden
        self.provider = cfg.JUDGE_PROVIDER  # "Google" oder "OpenAI"
        self.model = cfg.JUDGE_MODEL        # z.B. "gemini-2.0-flash"
        self.client = None
        
        # JSON-Schema für Structured Output laden
        # → Erzwingt, dass das LLM nur gültiges JSON im richtigen Format liefert
        self.schema = self._load_schema()
        
        # Client initialisieren (Google GenAI oder OpenAI)
        self._setup_client()

    def _load_schema(self) -> Optional[Dict[str, Any]]:
        """
        Lädt das JSON-Schema für Structured Output.
        
        Das Schema definiert die erwartete Struktur der Antwort.
        Gemini nutzt dies für "Constrained Decoding" - garantiert valides JSON.
        """
        schema_path = os.path.join(cfg.PROJECT_ROOT, "schema", "schema.json")
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Konnte Schema nicht laden: {schema_path} ({e})")
            return None

    def _setup_client(self):
        """
        Initialisiert den API-Client basierend auf JUDGE_PROVIDER.
        
        Für Google: Nutzt Vertex AI mit Service Account Credentials
        Für OpenAI: Nutzt API Key aus Umgebungsvariable
        """
        if self.provider == "Google":
            if not GOOGLE_AVAILABLE:
                logger.error("Google GenAI Client ist nicht verfügbar. Bitte installieren Sie das aktuelle Google SDK für KI-Modelle.")
                return
            
            # Vertex AI Konfiguration
            project_id = cfg.GEMINI_PROJECT_ID
            location = cfg.GEMINI_LOCATION  # z.B. "europe-west1"

            # Umgebungsvariablen setzen für SDK
            if project_id:
                os.environ["PROJECT_ID"] = project_id
            if cfg.GEMINI_CREDENTIALS:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cfg.GEMINI_CREDENTIALS

            try: 
                if project_id:
                    # Vertex AI Client mit Projekt-Authentifizierung
                    self.client = genai.Client(vertexai=True, project=project_id, location=location)
                else:
                    logger.warning("Meldung zum Judge: Kein Google Projekt ID konfiguriert.")
            except Exception as e:
                logger.error(f"Fehler bei der Initialisierung des 'Judge' mit dem Google GenAI Client: {e}")

        elif self.provider == "OpenAI":
            if not OPENAI_AVAILABLE:
                logger.error("OpenAI Client ist nicht verfügbar. Bitte installieren Sie das aktuelle OpenAI SDK.")
                return
            try:
                # OpenAI Client nutzt OPENAI_API_KEY Umgebungsvariable automatisch
                self.client = OpenAI()
            except Exception as e:
                logger.error(f"Fehler bei der Initialisierung des 'Judge' mit dem OpenAI Client: {e}")

    # -------------------------------------------------------------------------
    # HAUPTMETHODE: JSON REPARIEREN
    # -------------------------------------------------------------------------
            
    def heal_json(
        self, 
        file_bytes: bytes, 
        filename: str, 
        broken_json: Dict[str, Any], 
        error_list: List[Dict[str, Any]],
        template_coords: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Versucht fehlerhaftes JSON durch erneute KI-Analyse zu reparieren.
        
        Args:
            file_bytes: Das Originaldokument (PDF oder Bild) als Bytes
            filename: Dateiname (für MIME-Type Erkennung)
            broken_json: Das fehlerhafte JSON aus der ersten Extraktion
            error_list: Liste der Validierungsfehler 
                        [{"field": "date", "message": "Ungültiges Format"}, ...]
        
        Returns:
            Korrigiertes JSON-Dict oder None bei Fehler
        """
        if not self.client:
            logger.error("Judge Client nicht initialisiert. Der Prüfprozess kann nicht durchgeführt werden.")
            return None
        
        # ----- 1. Fehlerbericht erstellen -----
        # Formatiert alle Fehler als lesbare Liste für das LLM
        error_report = "\n".join([f"- Feld '{err['field']}': {err['message']}" for err in error_list])

        # ----- 2. Prompts laden -----
        # System-Prompt aus Datei (enthält Schema-Regeln und Reparatur-Anweisungen)
        system_prompt = load_prompt("judge_repair") 

        # User-Prompt mit konkreten Daten
        coords_hint = ""
        if template_coords:
             coords_hint = f"\nVERWENDE DIESE HILFS-KOORDINATEN (Template) ZUR ORIENTIERUNG:\n{json.dumps(template_coords, indent=2, ensure_ascii=False)}\n"
             
        user_prompt = f"""Hier sind die Daten, die repariert werden müssen:
                        Fehlerbericht:
                        {error_report}
                        {coords_hint}
                        Falsches JSON:{json.dumps(broken_json, indent=2, ensure_ascii=False)}:

                        Bitte repariere das JSON entsprechend den Validierungsregeln und der Datei die du erhalten hast.""" 
        
        try: 
            # ----- 3. API Aufruf je nach Provider -----
            if self.provider == "Google":
                return self._call_google_judge(system_prompt, user_prompt, file_bytes, filename)
            # TODO: OpenAI-Implementierung
            # elif self.provider == "OpenAI":
            #     return self._call_openai_judge(system_prompt, user_prompt)

        except Exception as e:
            logger.error(f"Judge Fehler bei der JSON Reparatur: {filename}: {e}")
            return None

    # -------------------------------------------------------------------------
    # PROVIDER-SPEZIFISCHE IMPLEMENTIERUNGEN
    # -------------------------------------------------------------------------
    
    def _call_google_judge(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        file_bytes: bytes, 
        filename: str
    ) -> Optional[Dict[str, Any]]:
        """
        Ruft Google Gemini API für die JSON-Reparatur auf.
        
        Nutzt Gemini's Multimodal-Fähigkeit: Text + Dokument gleichzeitig.
        Structured Output erzwingt valides JSON gemäß Schema.
        """
        # MIME-Type basierend auf Dateiendung
        mime_type = "application/pdf" if filename.lower().endswith(".pdf") else "image/png"

        # API-Konfiguration für Structured Output
        config_args = {
            "response_mime_type": "application/json",  # Erzwingt JSON-Antwort
            "system_instruction": system_prompt        # Reparatur-Anweisungen
        }

        # Optional: Schema für Constrained Decoding
        # → Gemini generiert nur JSON das exakt dem Schema entspricht
        if self.schema:
            config_args["response_schema"] = clean_json_schema(self.schema)

        # API-Aufruf mit Text + Dokument
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                user_prompt,  # Die Reparatur-Anfrage
                # Das Originaldokument als Binary-Part
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
            ],
            config=config_args
        )

        # Antwort parsen
        if response.text:
            return json.loads(response.text)
        return None
