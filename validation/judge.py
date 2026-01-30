import json
import logging
import os
import base64
from typing import List, Dict, Any, Optional
import config.config as cfg
# Clients laden
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


class Judge:
    def __init__(self):
        self.provider = cfg.JUDGE_PROVIDER
        self.model = cfg.JUDGE_MODEL
        self.client = None
        self._setup_client()

    def _setup_client(self):
        """Initialisiert den Client basierend auf dem konfigierten Provider in Config/config.py"""

        if self.provider == "Google":
            if not GOOGLE_AVAILABLE:
                logger.error("Google GenAI Client ist nicht verfügbar. Bitte installieren Sie das aktuelle Google SDK für KI-Modelle.")
                return
            
            project_id = cfg.GEMINI_PROJECT_ID
            location = cfg.GEMINI_LOCATION

            try: 
                if project_id:
                    self.client= genai.Client(vertexai=True, project_id=project_id, location=location)
                else:
                    logger.warning("Meldung zum Judge: Kein Google Projekt ID konfiguriert.")
            except Exception as e:
                logger.error(f"Fehler bei der Initialisierung des 'Judge' mit dem Google GenAI Client: {e}")

        elif self.provider == "OpenAI":
            if not OPENAI_AVAILABLE:
                logger.error("OpenAI Client ist nicht verfügbar. Bitte installieren Sie das aktuelle OpenAI SDK.")
                return
            try:
                self.client = OpenAI()
            except Exception as e:
                logger.error(f"Fehler bei der Initialisierung des 'Judge' mit dem OpenAI Client: {e}")
            
    def heal_json(self, file_bytes: bytes, filename:str, broken_json:Dict[str, Any], error_list: List[Dict[str,Any]]) -> Optional[Dict[str, Any]]:
        """Versucht ein JSON zu reparieren, indem es das Dokument und die Fehler an den KI-Juge sendet."""

        if not self.client:
            logger.error("Judge Client nicht initialisiert. Der Prüfprozess kann nicht durchgeführt werden.")
            return None
        
        # 1. Prompt vorbereiten
        error_report = "\n".join([f"- Feld '{err['field']}': {err['message']}" for err in error_list])

        system_prompt = """Du bist ein Experte für Daten-Korrektur (Data Remediation). 
                            Dein Job ist es, fehlerhafte JSON-Daten einer OCR-Extraktion zu reparieren.
                            Du erhältst:
                            1. Das Original-Dokument (Bild/PDF).
                            2. Das extrahierte JSON, das Validierungsfehler enthält.
                            3. Eine Liste der Fehler.

                            Deine Aufgabe:
                            - Analysiere das Bild an den betroffenen Stellen.
                            - Korrigiere die Werte im JSON, damit sie den Validierungsregeln entsprechen (z.B. Datumsformat, Menge > 0, Preisformat).
                            - Du erhältst ein JSON-Schema zur Orientierung.""" 

        user_prompt = f"""Hier sind die Daten, die repariert werden müssen:
                        Fehlerbericht:
                        {error_report}
                        Falsches JSON:{json.dumps(broken_json, indent=2, ensure_ascii=False)}:

                        Bitte repariere das JSON entsprechend den Validierungsregeln und der Datei die du erhalten hast.""" 
        
        try: 
            # 2. API Aufruf 
            if self.provider == "Google":
                return self._call_google_judge(system_prompt, user_prompt, file_bytes, filename)
            #elif self.provider == "OpenAI":
                #return self._call_openai_judge(system_prompt, user_prompt )

        except Exception as e:
            logger.error(f"Judge Fehler bei der JSON Reparatur: {filename}: {e}")
            return None
    
    def _call_google_judge(self, system_prompt,user_prompt, file_bytes:bytes, filename):
        """Aktiviert Google GenAI für den Judge Prozess."""
        mime_type = "application/pdf" if filename.lower().endswith(".pdf") else "image/png"

        # Konfiguration für JSON Output

        response = self.client.models.generate_content(
            model =self.model,
            contents=[types.Content(
                    role="user",
                    parts=[
                        types.Part(text=user_prompt),
                        types.Part(
                            inline_data=types.Blob(
                                mime_type=mime_type,
                                data=file_bytes

                            )
                        )
                    ]
                    
                )
            ],
            config= types.GenerationContentConfig(response_mime_type="application/json",system_instructions=system_prompt
        )
        )

        if response.text:
            return json.loads(response.text)
        return None
    
    



