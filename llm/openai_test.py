import json
import os
from mistralai import Mistral
from dotenv import load_dotenv
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

# load environment variables from .env if present
load_dotenv()

# Basis-Verzeichnis dieses Skripts ermitteln
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Create Jinja2 environment pointing to a 'templates' directory next to this file
env = Environment(loader=FileSystemLoader(os.path.join(BASE_DIR, 'templates')))

# Verwende Mistral Client statt OpenAI, da openai modul fehlt
api_key = os.getenv("MISTRAL_API_KEY")
client = Mistral(api_key=api_key)

# Lädt das JSON Schema aus eine separaten Datei
def get_extraction_schema():
    schema_path = os.path.join(BASE_DIR, 'schema.json')
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def extract_and_generate_xml(markdown_text):
    """
    Hauptfunktion, die von der App aufgerufen wird.
    Nimmt Markdown entgegen und gibt (JSON-Daten, XML-String) zurück.
    """
    schema = get_extraction_schema()
    
    # System Prompt mit Schema für Mistral
    system_prompt = f"""
    Du bist ein spezialisierter KI-Assistent für die Datenextraktion.
    Extrahiere Daten aus dem Dokument und antworte ausschließlich mit einem validen JSON-Objekt, das diesem Schema entspricht:
    {json.dumps(schema, ensure_ascii=False)}
    """

    try:
        response = client.chat.complete(
            model="mistral-large-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Hier ist der Dokumententext:\n\n{markdown_text}"}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        data = json.loads(content)
    except Exception as e:
        return {}, f"Fehler bei der KI-Extraktion: {e}"

    # 2. Hardcoded Rules (Der Wächter)
    # Hier reparierst du die "Gefahrenstellen" bevor sie ins XML kommen
    if 'SupplierConfirmation' in data and 'Details' in data['SupplierConfirmation']:
        for detail in data['SupplierConfirmation']['Details']:
            # Regel: Position * 10
            try:
                if 'number' in detail:
                    raw_num = int(detail['number'])
                    detail['number'] = str(raw_num * 10)
                    if 'CorrespondenceDetail' in detail and 'number' in detail['CorrespondenceDetail']:
                        detail['CorrespondenceDetail']['number'] = str(raw_num * 10)
            except:
                pass 

            # Regel: Menge auf 0 wenn Dezimal
            if 'totalQuantity' in detail and 'amount' in detail['totalQuantity']:
                amount = str(detail['totalQuantity']['amount'])
                if ',' in amount or '.' in amount:
                    detail['totalQuantity']['amount'] = "0" 

    # 3. XML Generierung mit Jinja2
    try:
        template = env.get_template('template.xml.j2')
        xml_output = template.render(data=data, timestamp=datetime.now().isoformat())
    except Exception as e:
        xml_output = f"Fehler bei der XML Generierung: {e}"

    return data, xml_output