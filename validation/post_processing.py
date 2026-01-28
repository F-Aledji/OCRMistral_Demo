from datetime import datetime

def enforce_business_rules(data):
    """Wendet Geschäftsregeln auf die extrahierten Daten an. Unterstützt sowohl einzelne 'SupplierConfirmation'-Objekte 
    als auch 'documents'-Liste"""

    # Prüfung 1: Mehrere SupplierConfirmations (Liste)
    if 'documents' in data and isinstance(data['documents'], list):
        for doc in data['documents']:
            # rekursiver aufruf:
            enforce_business_rules(doc)
        return data
    
    # Prüfung 2: Einzelnes SupplierConfirmation (Objekt)
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
    """Erstellt XML basierend auf den Daten und dem Template. 
    Gibt nun eine LISTE von XML-Strings zurück, um mehrere Dokumente im selben JSON zu unterstützen.
    """
    xml_results = []
    try:
        template = env.get_template('schema/template.xml.j2')
        timestamp_str = datetime.now().isoformat()
        
        # Fall A: 'documents' Liste vorhanden (Neues Schema)
        if 'documents' in data and isinstance(data['documents'], list):
            # Wenn Liste leer ist, passiert nichts -> leere Liste zurück
            for doc in data['documents']:
                # Wir gehen davon aus, dass 'doc' die Struktur { "SupplierConfirmation": ... } hat
                # Das Template erwartet 'data.SupplierConfirmation...' 
                rendered_xml = template.render(data=doc, timestamp=timestamp_str)
                xml_results.append(rendered_xml)

        # Fall B: Einzelnes Objekt (Legacy Support oder Fallback)
        # Wir prüfen ob es direkt SupplierConfirmation ist, um Dopplung zu vermeiden falls 'documents' existiert
        elif 'SupplierConfirmation' in data:
            rendered_xml = template.render(data=data, timestamp=timestamp_str)
            xml_results.append(rendered_xml)
        
        # Fall C: Fallback für leere/falsche Daten, wenn Fall A auch nicht griff
        if not xml_results and not ('documents' in data and isinstance(data['documents'], list)):
             # Versuchen wir es einfach mit den Rohdaten, vielleicht klappt das Rendering (oder führt zum Fehler)
             rendered_xml = template.render(data=data, timestamp=timestamp_str)
             xml_results.append(rendered_xml)

        return xml_results

    except Exception as e:
        # Um kompatibel zu bleiben geben wir eine Liste mit 1 Fehler-String zurück
        return [f"Fehler bei der XML Generierung: {e}"]
