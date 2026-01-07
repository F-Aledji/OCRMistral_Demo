# =============================================================================
# AUSKOMMENTIERT - Nicht in Verwendung
# Diese Datei enthält unfertigen Gemini/Vertex AI Code mit undefinierten Variablen
# Die aktive LLM-Logik befindet sich in openai_test.py
# =============================================================================

"""
import os
import json
import vertexai
from vertexai.generative_models import GenerativeModel
from google import genai
from extraction.convert import json_to_xml
from dotenv import load_dotenv


load_dotenv()

# Initialize Vertex AI
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "vertex_credentials.json"
vertexai.init(project=os.getenv("project_id"), location="europe-west4")
gemini_model = GenerativeModel("gemini-3-0-pro-preview")



Example Instructions - Customize this for your use case:

SYSTEM_INSTRUCTIONS = '''
Du bist ein Experte für Datenextraktion aus OCR-Texten.
Deine Aufgabe ist es, die folgenden Informationen aus dem Text zu extrahieren:
- Field 1: Beschreibung was extrahiert werden soll
- Field 2: Beschreibung was extrahiert werden soll

Antworte NUR mit einem validen JSON-Objekt im angegebenen Schema.
Wenn eine Information nicht gefunden wird, setze den Wert auf null.
'''
"""


"""
# =============================================================================
# Gemini Vertex AI
# =============================================================================

# SYSTEM_INSTRUCTIONS =# TODO: Define your extraction instructions here
prompt = f"{instructions}\n\nErwartetes JSON-Schema:\n{schema}\n\nText:\n{ocr_text}"

class GeminiLLM:
  
    
    def __init__(self):
        self.model = gemini_model
        self.client = genai.Client(vertexai=True, project=gemini_project, location=gemini_location, api_key=gemini_api_key)
    
    ## Extrahiert strukturierte Daten aus OCR-Text.
    def extract_structured_response(self, ocr_text, instructions=None, schema=None):
       
        Args:
            ocr_text: Der extrahierte Text aus Mistral OCR
            instructions: Optional - Überschreibt SYSTEM_INSTRUCTIONS
            schema: Optional - Überschreibt EXTRACTION_SCHEMA
        
        Returns:
            str: JSON-Response vom LLM
 
        instructions = instructions or SYSTEM_INSTRUCTIONS
        schema = schema or EXTRACTION_SCHEMA
        
        
        
        # TODO: Implement Gemini API call
        # response = self.client.models.generate_content(
        #     model=self.model,
        #     contents=prompt
        # )
        # return response.text
        response = self.client.models.generate_content(
            model = self.model,
            contents = prompt
        )
        return response.text
        raise NotImplementedError("Gemini API noch nicht implementiert")
        self.client.close()

    def get_extraction_schema():
  
    with open('supplier_confirmation_schema.json', 'r', encoding='utf-8') as f:
        return json.load(f)
"""