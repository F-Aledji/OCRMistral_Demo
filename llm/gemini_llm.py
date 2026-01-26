import os
import json
import logging
from typing import Any, Dict
from google import genai
from google.genai import types
from llm.base_llm import BaseLLM
import config.config as cfg

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTIONS = """Du bist ein Markdown zu JSON parser. Du erhältst Markdown-Text und eine JSON-Schema Definition. Deine Aufgabe ist es, die relevanten Daten aus dem Markdown basierend des Schemas zu extrahieren und sie in einem validen JSON-Format zurückzugeben.
"""

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
             logger.info(f"Gemini LLM Client erfolgreich konfiguriert für Projekt '{self.project_id}'.")
        except Exception as e:
             logger.error(f"Gemini Client Init Error: {e}")
             raise RuntimeError(f"Gemini LLM Client konnte nicht initialisiert werden: {e}")

    def get_json_extraction(self, markdown_text: str, extraction_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Ruft Gemini API auf um strukturierte JSON-Daten aus Markdown zu extrahieren."""
        if not self.client:
            logger.warning("Gemini Client not initialized.")
            return {}

        prompt = f"""
        Extract data from the following markdown text based on the provided schema.
        
        Markdown Text:
        {markdown_text}
        """

        try:
            # Schema Cleaning: Gemini expects a slightly different schema structure sometimes, 
            # but standard JSON schema usually works with recent Vertex AI versions.
            # Removing '$schema' key if present as it might cause issues.
            qs = extraction_schema.copy()
            if '$schema' in qs:
                del qs['$schema']

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=qs,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.LOW),
                    system_instruction=SYSTEM_INSTRUCTIONS
                )
            )
            
            if response.text:
                return json.loads(response.text)
            return {}
        except Exception as e:
             print(f"Gemini LLM Error: {e}")
             return {}
