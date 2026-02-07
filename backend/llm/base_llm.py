from abc import ABC, abstractmethod
import json
import os
from jinja2 import Environment, FileSystemLoader
from backend.validation.post_processing import generate_xml_from_data

class BaseLLM(ABC):
    def __init__(self, project_root):
        self.project_root = project_root
        self.env = Environment(loader=FileSystemLoader(project_root))

        """Lädt das JSON Schema aus document_schema.json im Backend-Schema-Ordner"""
        # Pfad: backend/llm/BaseLLM.py -> backend/schema/document_schema.json
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        schema_path = os.path.join(base_dir, 'schema', 'document_schema.json')
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @abstractmethod
    def get_json_extraction(self, markdown_text, extraction_schema):
        """Muss von der Subklasse implementiert werden. Gibt das extrahierte JSON (dict) zurück."""
        pass

    def extract_and_generate_xml(self, markdown_text):
        """
        Hauptfunktion
        Nimmt Markdown entgegen und gibt (JSON-Daten, XML-String) zurück.
        """
        extraction_schema = self.get_extraction_schema()
        
        # API Aufruf (Subklasse)
        data = self.get_json_extraction(markdown_text, extraction_schema)
        
        if not data:
             return {}, "Keine Daten extrahiert."

        # XML
        xml_output = generate_xml_from_data(data, self.env)

        return data, xml_output
