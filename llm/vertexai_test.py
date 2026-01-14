import json
import os
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

# load environment variables from .env if present
load_dotenv()

# Basis-Verzeichnis dieses Skripts ermitteln (llm/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Projekt-Root (eine Ebene höher)
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Jinja2 Environment zeigt auf Projekt-Root für template.xml.j2
env = Environment(loader=FileSystemLoader(PROJECT_ROOT))

client = genai.Client()


# Lädt das JSON Schema aus schema.json im Projekt-Root
def get_extraction_schema():
    schema_path = os.path.join(PROJECT_ROOT, 'schema.json')
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)

SYSTEM_INSTRUCTIONS = ""

"""
# Flash Modell mit normalen Reasoning Aufwand
def get_json_extraction_low(markdown_text, extraction_schema):
    #Ruft Gemini auf um strukturierte JSON-Daten aus Markdown zu extrahieren.
    response = client.models.generate_content(
        model="gemini-3-pro-preview",
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.HIGH # Hoher Reasoning-Aufwand
            )
"""

# 1. KI Call mit Schema - akzeptiert markdown_text und schema als Parameter
def get_json_extraction_high(markdown_text, extraction_schema):
    """Ruft Gemini auf um strukturierte JSON-Daten aus Markdown zu extrahieren."""
    response = client.models.generate_content(
        model="gemini-3-pro-preview",
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH),
            system_instruction=SYSTEM_INSTRUCTIONS 
        ), 
        contents=markdown_text
    )
    return response

def extract_and_generate_xml(markdown_text):
    """
    Hauptfunktion, die von der App aufgerufen wird.
    Nimmt Markdown entgegen und gibt (JSON-Daten, XML-String) zurück.
    """
    extraction_schema = get_extraction_schema()
    
    # API Aufruf
    #response_low = get_json_extraction_high(markdown_text, extraction_schema)
    response_high = get_json_extraction_high(markdown_text, extraction_schema)
    
    # Response parsen (OpenAI Responses API Format)
    #content = response_low.output_text
    content = response_high.output_text
    
    if not content:
        return {}, "Keine Daten extrahiert."

    data = json.loads(content)

    # 2. Hardcoded Rules (Der Wächter)
    # Hier reparierst du die "Gefahrenstellen" bevor sie ins XML kommen
    # Prüfen ob die Struktur überhaupt existiert um Fehler zu vermeiden
    if 'SupplierConfirmation' in data and 'Details' in data['SupplierConfirmation']:
        for detail in data['SupplierConfirmation']['Details']:
            # Regel: Position * 10
            try:
                if 'number' in detail:
                    raw_num = int(detail['number'])
                    detail['number'] = str(raw_num * 10)
                    # Prüfen ob CorrespondenceDetail existiert
                    if 'CorrespondenceDetail' in detail and 'number' in detail['CorrespondenceDetail']:
                        detail['CorrespondenceDetail']['number'] = str(raw_num * 10)
            except Exception:
                pass # Fallback behalten

            # Regel: Menge auf 0 wenn Dezimal
            if 'totalQuantity' in detail and 'amount' in detail['totalQuantity']:
                amount = str(detail['totalQuantity']['amount'])
                if ',' in amount or '.' in amount:
                    # Hier könntest du auch loggen: "Warnung: Dezimalmenge gefunden!"
                    detail['totalQuantity']['amount'] = "0" 

    # 3. XML Generierung mit Jinja2
    try:
        template = env.get_template('template.xml.j2')
        xml_output = template.render(data=data, timestamp=datetime.now().isoformat())
    except Exception as e:
        xml_output = f"Fehler bei der XML Generierung: {e}"

    return data, xml_output