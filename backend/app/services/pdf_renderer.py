# =============================================================================
# PDF RENDERER SERVICE
# =============================================================================
# Zeichnet Bounding Boxes und Labels ins PDF ("Burn-in").
# Das Ergebnis ist ein neues PDF mit den Annotationen als sichtbare Rechtecke.
#
# Verwendet PyMuPDF (fitz) für die PDF-Bearbeitung.
# =============================================================================

import fitz  # PyMuPDF
from typing import Dict, Any, List, Tuple
from uuid import UUID
import os


# Farben für verschiedene Feldtypen (RGB, Werte 0-1)
FIELD_COLORS: Dict[str, Tuple[float, float, float]] = {
    "ba_number": (0.133, 0.773, 0.369),      # Grün
    "vendor_name": (0.231, 0.510, 0.965),    # Blau
    "document_date": (0.918, 0.702, 0.031),  # Gelb
    "total_value": (0.937, 0.267, 0.267),    # Rot
    "document_type": (0.545, 0.361, 0.965),  # Lila
}

DEFAULT_COLOR = (0.580, 0.639, 0.718)  # Grau


def render_annotated_pdf(
    original_pdf_bytes: bytes,
    annotations: Dict[str, Any]
) -> bytes:
    """
    Erstellt ein PDF mit eingezeichneten Bounding Boxes.
    
    Args:
        original_pdf_bytes: Das Original-PDF als Bytes
        annotations: Dict mit Feld-Annotationen, z.B.:
            {
                "ba_number": {
                    "value": "BA123456",
                    "bbox": {"page": 0, "x0": 100, "y0": 200, "x1": 180, "y1": 212}
                }
            }
    
    Returns:
        Das annotierte PDF als Bytes
    """
    # PDF öffnen
    doc = fitz.open(stream=original_pdf_bytes, filetype="pdf")
    
    # Für jedes annotierte Feld
    for field_name, annotation in annotations.items():
        if not annotation or "bbox" not in annotation or not annotation["bbox"]:
            continue
            
        bbox = annotation["bbox"]
        value = annotation.get("value", field_name)
        
        # Seite holen
        page_num = bbox.get("page", 0)
        if page_num >= len(doc):
            continue
            
        page = doc[page_num]
        
        # Koordinaten
        x0 = bbox.get("x0", 0)
        y0 = bbox.get("y0", 0)
        x1 = bbox.get("x1", x0 + 50)
        y1 = bbox.get("y1", y0 + 15)
        
        # Farbe wählen
        color = FIELD_COLORS.get(field_name, DEFAULT_COLOR)
        
        # Rechteck zeichnen (Rahmen)
        rect = fitz.Rect(x0, y0, x1, y1)
        page.draw_rect(
            rect,
            color=color,
            width=1.5,
            fill=None,  # Kein Füllmuster
            overlay=True
        )
        
        # Hintergrund für Label (leicht transparent)
        label_text = f"{field_name}: {value}"
        label_height = 12
        label_rect = fitz.Rect(x0, y0 - label_height - 2, x0 + len(label_text) * 5, y0 - 2)
        page.draw_rect(
            label_rect,
            color=None,
            fill=color,
            overlay=True
        )
        
        # Text-Label einfügen
        page.insert_text(
            (x0 + 2, y0 - 4),
            label_text,
            fontsize=9,
            color=(1, 1, 1),  # Weiß
            overlay=True
        )
    
    # PDF als Bytes zurückgeben
    output_bytes = doc.tobytes()
    doc.close()
    
    return output_bytes


def create_annotated_pdf_file(
    original_pdf_path: str,
    annotations: Dict[str, Any],
    output_path: str
) -> str:
    """
    Convenience-Funktion: Liest PDF von Datei, annotiert, speichert.
    
    Args:
        original_pdf_path: Pfad zum Original-PDF
        annotations: Die Annotationen
        output_path: Wo das Ergebnis gespeichert werden soll
    
    Returns:
        Pfad zur annotierten Datei
    """
    with open(original_pdf_path, "rb") as f:
        original_bytes = f.read()
    
    annotated_bytes = render_annotated_pdf(original_bytes, annotations)
    
    with open(output_path, "wb") as f:
        f.write(annotated_bytes)
    
    return output_path
