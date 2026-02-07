import base64
import os
import json
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Support both: running from project root (backend.X) and from backend dir (X)
try:
    from backend.extraction.base_ocr import BaseOCR
    from backend.config.schema_utils import clean_json_schema
    from backend.config.prompt_loader import load_prompt
except ImportError:
    from extraction.base_ocr import BaseOCR
    from config.schema_utils import clean_json_schema
    from config.prompt_loader import load_prompt

load_dotenv()

logger = logging.getLogger(__name__)

GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if GOOGLE_APPLICATION_CREDENTIALS:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS

PROJECT_ID = "ocr-pipeline-weinmannschanz"
LOCATION = "global"

# Komplexer Prompt aus Datei laden
SYSTEM_PROMPT = load_prompt("ocr_extraction")
# Einfacher Prompt - bleibt inline
USER_PROMPT = "Achte auf die Einhaltung der Geschäftsregeln. Extrahiere alle relevanten Daten aus dem Dokument."


#--- OCR Engine Klasse für Gemini über Google Cloud ---
class GeminiOCR(BaseOCR):
    def __init__(self, service_account_json_path, project_id, location, model_name="gemini-3-flash-preview"):
        super().__init__()
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        
        if project_id:
            os.environ["PROJECT_ID"] = project_id
        # Falls ein expliziter Pfad übergeben wird, als GOOGLE_APPLICATION_CREDENTIALS setzen
        if service_account_json_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_json_path
        
        # Initialisierung des neuen Google Gen AI Clients
        try:
            self.client = genai.Client(
                vertexai=True, 
                project=project_id, 
                location=location
            )
            logger.info(f"Google Gen AI Client (v1) erfolgreich konfiguriert für Projekt '{project_id}'.")
        except Exception as e:
            logger.error(f"Fehler bei der Konfiguration: {e}")
            raise RuntimeError(f"Google Gen AI Client konnte nicht initialisiert werden: {e}")

    def process_pdf(self, file_bytes, stream=False, json_schema=None, hints=None):
        return self._process_content(file_bytes, "application/pdf", stream, json_schema, hints)

    def process_image(self, file_bytes, stream=False, json_schema=None, hints=None):
        return self._process_content(file_bytes, "image/jpeg", stream, json_schema, hints)

    def _process_content(self, file_bytes, mime_type, stream=False, json_schema=None, hints=None):
        """Interner interner Helfer zur Verarbeitung von Inhalten mit optionaler JSON-Durchsetzung"""
        
        # Config Setup
        config_args = {
            "system_instruction": SYSTEM_PROMPT,
            "thinking_config": types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH)
        }

        # Wenn json_schema übergeben wird, Structured Output erzwingen
        if json_schema:
            config_args["response_mime_type"] = "application/json"
            config_args["response_schema"] = clean_json_schema(json_schema)
            # Bei Structured Output macht Streaming oft weniger Sinn oder ist anders, 
            # aber wir lassen den Parameter durch, falls unterstützt.
        
        # Method selection
        method = self.client.models.generate_content_stream if stream else self.client.models.generate_content
        
        # Standard-Aufruf (SDK): client.models.generate_content(model=..., contents=[...], config={...})
        # Hier: wir senden Text + Datei als Part und erzwingen bei Bedarf Structured Output via Schema.
        response = method(
            model=self.model_name,
            contents=[
                USER_PROMPT + (f"\n\nHINWEIS (Layout-Daten): {json.dumps(hints, indent=2)}" if hints else ""),
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
            ],
            config=config_args
        )
       
        return response

    # Legacy Aliases
    def gemini_ocr_pdf_base64(self, file_bytes, stream=False):
        return self.process_pdf(file_bytes, stream)

    def gemini_ocr_image_base64(self, file_bytes, stream=False):
        return self.process_image(file_bytes, stream)