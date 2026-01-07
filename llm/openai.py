# =============================================================================
# AUSKOMMENTIERT - Nicht in Verwendung
# Diese Datei enthält unfertige Azure/OpenAI Klassen mit undefinierten Variablen
# Die aktive LLM-Logik befindet sich in openai_test.py
# =============================================================================

"""
from openai import AzureOpenAI, OpenAI
from dotenv import load_dotenv

load_dotenv()

#Initialize Azure OpenAI and OpenAI
openai_api_key = os.getenv("OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")


prompt = f"{instructions}\n\nErwartetes JSON-Schema:\n{schema}\n\nText:\n{ocr_text}"

class AzureLLM:
    Klasse um Azure OpenAI API zu nutzen
    
    def __init__(self, api_key, endpoint, deployment_id, api_version):
        self.deployment_id = deployment_id
        self.client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version
        )

    def extract_structured_response(self, ocr_text, instructions=None, schema=None):
        
        Extrahiert strukturierte Daten aus OCR-Text.
        
        Args:
            ocr_text: Der extrahierte Text aus Mistral OCR
            instructions: Optional - Überschreibt SYSTEM_INSTRUCTIONS
            schema: Optional - Überschreibt EXTRACTION_SCHEMA
        
        Returns:
            str: JSON-Response vom LLM
        
        instructions = instructions or SYSTEM_INSTRUCTIONS
        schema = schema or EXTRACTION_SCHEMA
        
        system_prompt = f"{instructions}\n\nErwartetes JSON-Schema:\n{schema}"
        
        response = self.client.chat.completions.create(
            model=self.deployment_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": ocr_text}
            ],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content


class OpenAILLM:
    Klasse um OpenAI API zu nutzen
    
    def __init__(self, model="gpt-5-mini"):
        self.model = model
        self.client = OpenAI(api_key=openai_api_key)
    
    def extract_structured_response(self, ocr_text, instructions=None, schema=None):
        
        Extrahiert strukturierte Daten aus OCR-Text.
        
        Args:
            ocr_text: Der extrahierte Text aus Mistral OCR
            instructions: Optional - Überschreibt SYSTEM_INSTRUCTIONS
            schema: Optional - Überschreibt EXTRACTION_SCHEMA
        
        Returns:
            str: JSON-Response vom LLM
        
        instructions = instructions or SYSTEM_INSTRUCTIONS
        schema = schema or EXTRACTION_SCHEMA
        
        system_prompt = f"{instructions}\n\nErwartetes JSON-Schema:\n{schema}"
        
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": "high"},
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": ocr_text}
            ]
        )
        return response.choices[0].message.content
"""