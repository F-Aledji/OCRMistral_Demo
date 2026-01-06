import os
import json
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from openai import AzureOpenAI, OpenAI
# from google import genai  # Uncomment when using Gemini


def json_to_xml(json_data, root_name="extraction"):
    """
    Konvertiert ein JSON-Objekt (dict oder str) zu einem XML-String.
    
    Args:
        json_data: JSON als dict oder string
        root_name: Name des Root-Elements (default: "extraction")
    
    Returns:
        str: Formatierter XML-String
    
    Example:
        json_data = {"name": "Max", "items": [{"id": 1}, {"id": 2}]}
        xml_str = json_to_xml(json_data, root_name="document")
        # Output:
        # <?xml version="1.0" ?>
        # <document>
        #   <name>Max</name>
        #   <items>
        #     <item><id>1</id></item>
        #     <item><id>2</id></item>
        #   </items>
        # </document>
    """
    if isinstance(json_data, str):
        json_data = json.loads(json_data)
    
    def _build_xml(parent, data):
        if isinstance(data, dict):
            for key, value in data.items():
                child = SubElement(parent, key)
                _build_xml(child, value)
        elif isinstance(data, list):
            for item in data:
                child = SubElement(parent, "item")
                _build_xml(child, item)
        else:
            parent.text = str(data) if data is not None else ""
    
    root = Element(root_name)
    _build_xml(root, json_data)
    
    # Pretty print
    rough_string = tostring(root, encoding="unicode")
    parsed = minidom.parseString(rough_string)
    return parsed.toprettyxml(indent="  ")



# =============================================================================
# JSON SCHEMA TEMPLATE - Define your extraction structure here
# =============================================================================
"""
Example JSON Schema - Customize this for your use case:

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "field_1": {"type": "string", "description": "Description of field 1"},
        "field_2": {"type": "number", "description": "Description of field 2"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "string"}
                }
            }
        }
    },
    "required": ["field_1", "field_2"]
}
"""

EXTRACTION_SCHEMA = {
    # TODO: Define your JSON schema here
}

# =============================================================================
# SYSTEM INSTRUCTIONS TEMPLATE - Define your LLM instructions here
# =============================================================================
"""
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

SYSTEM_INSTRUCTIONS = """
# TODO: Define your extraction instructions here
"""


# =============================================================================
# LLM CLASSES
# =============================================================================


class GeminiLLM:
    """Klasse um Gemini API zu nutzen"""
    
    def __init__(self, api_key, model="gemini-2.0-flash"):
        self.model = model
        # TODO: Initialize Gemini client
        # self.client = genai.Client(api_key=api_key)
        pass
    
    def extract_structured_response(self, ocr_text, instructions=None, schema=None):
        """
        Extrahiert strukturierte Daten aus OCR-Text.
        
        Args:
            ocr_text: Der extrahierte Text aus Mistral OCR
            instructions: Optional - Überschreibt SYSTEM_INSTRUCTIONS
            schema: Optional - Überschreibt EXTRACTION_SCHEMA
        
        Returns:
            str: JSON-Response vom LLM
        """
        instructions = instructions or SYSTEM_INSTRUCTIONS
        schema = schema or EXTRACTION_SCHEMA
        
        prompt = f"{instructions}\n\nErwartetes JSON-Schema:\n{schema}\n\nText:\n{ocr_text}"
        
        # TODO: Implement Gemini API call
        # response = self.client.models.generate_content(
        #     model=self.model,
        #     contents=prompt
        # )
        # return response.text
        raise NotImplementedError("Gemini API noch nicht implementiert")