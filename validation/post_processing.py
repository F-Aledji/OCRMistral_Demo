from datetime import datetime

def enforce_business_rules(data):
    """Wendet Geschäftsregeln auf die extrahierten Daten an."""
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
    return data

def generate_xml_from_data(data, env):
    """Erstellt XML basierend auf den Daten und dem Template."""
    try:
        template = env.get_template('schema/template.xml.j2')
        xml_output = template.render(data=data, timestamp=datetime.now().isoformat())
        return xml_output
    except Exception as e:
        return f"Fehler bei der XML Generierung: {e}"
