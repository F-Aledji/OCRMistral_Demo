import os
import json
import logging
from typing import Any, Dict
from google import genai
from google.genai import types

try:
    from backend.llm.base_llm import BaseLLM
    from backend.utils.schema_utils import clean_json_schema
    from backend.config import config as cfg
except ImportError:
    from llm.base_llm import BaseLLM
    from utils.schema_utils import clean_json_schema
    from config import config as cfg

logger = logging.getLogger(__name__)

# Einfacher Prompt - bleibt inline
SYSTEM_INSTRUCTIONS = ""

class GeminiLLM(BaseLLM):
    def __init__(self, project_root: str):
        super().__init__(project_root)
        self.project_id = cfg.GEMINI_PROJECT_ID
        self.location = cfg.GEMINI_LOCATION
        self.model_name = cfg.GEMINI_LLM_MODEL
        
        if self.project_id:
             os.environ["PROJECT_ID"] = self.project_id
        if cfg.GEMINI_CREDENTIALS:
             os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cfg.GEMINI_CREDENTIALS

        try:
             self.client = genai.Client(
                vertexai=True, 
                project=self.project_id, 
                location=self.location
            )
             logger.info(f"Gemini Flash Client erfolgreich konfiguriert für Projekt '{self.project_id}'.")
        except Exception as e:
             logger.error(f"Gemini Flash Client Init Error: {e}")
             raise RuntimeError(f"Gemini Flash Client konnte nicht initialisiert werden: {e}")

    def get_json_extraction(self, coordinates,  extraction_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Ruft Gemini API auf um aus eingezeichnete Koordinaten Daten zu extrahieren."""
        if not self.client:
            logger.warning("Gemini Flash Client not initialized.")
            return {}

        prompt = "" # Hier der Prompt um die Koordinaten zu verarbeiten und die Daten zu speichern

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=clean_json_schema(extraction_schema),
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.LOW),
                    system_instruction=SYSTEM_INSTRUCTIONS
                )
            )
            
            if response.text:
                return json.loads(response.text)
            return {}
        except Exception as e:
             print(f"Gemini Flash Client Error: {e}")
             return {}
