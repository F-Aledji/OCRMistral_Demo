import os
import json
from typing import Any, Dict
from dotenv import load_dotenv
from google import genai
from google.genai import types
from llm.base_llm import BaseLLM

load_dotenv()

class GeminiLLM(BaseLLM):
    def __init__(self, project_root: str):
        super().__init__(project_root)
        self.project_id = os.getenv("GEMINI_PROJECT_ID")
        self.location = os.getenv("GEMINI_LOCATION", "global")
        self.model_name = "gemini-3-pro-preview"
        
        service_account_path = os.getenv("GEMINI_SERVICE_ACCOUNT_PATH")
        if self.project_id:
             os.environ["PROJECT_ID"] = self.project_id
        if service_account_path:
             os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path

        try:
             self.client = genai.Client(
                vertexai=True, 
                project=self.project_id, 
                location=self.location
            )
        except Exception as e:
             print(f"Gemini Client Init Error: {e}")
             self.client = None

    def get_json_extraction(self, markdown_text: str, extraction_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Ruft Gemini API auf um strukturierte JSON-Daten aus Markdown zu extrahieren."""
        if not self.client:
            print("Gemini Client not initialized.")
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
                        thinking_level=types.ThinkingLevel.LOW)
                )
            )
            
            if response.text:
                return json.loads(response.text)
            return {}
        except Exception as e:
             print(f"Gemini LLM Error: {e}")
             return {}
