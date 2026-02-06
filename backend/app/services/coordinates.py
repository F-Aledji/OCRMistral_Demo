# =============================================================================
# KOORDINATEN-KONVERTER
# =============================================================================
# Konvertiert zwischen verschiedenen Koordinatensystemen:
# - Gemini API: 0-1000 (normalisiert)
# - PDF: Punkte (1 Punkt = 1/72 Zoll)
# - Canvas: Pixel (abhängig vom Zoom)
# =============================================================================


def gemini_to_pdf(
    x_gemini: float, 
    y_gemini: float, 
    page_width_pts: float, 
    page_height_pts: float
) -> tuple[float, float]:
    """
    Konvertiert Gemini-Koordinaten (0-1000) zu PDF-Punkten.
    
    Gemini normalisiert alle Koordinaten auf einen Bereich von 0 bis 1000.
    Das bedeutet:
    - x=0 ist der linke Rand
    - x=1000 ist der rechte Rand
    - y=0 ist der obere Rand (ACHTUNG: Bei PDFs ist y=0 oft unten!)
    - y=1000 ist der untere Rand
    
    Args:
        x_gemini: X-Koordinate von Gemini (0-1000)
        y_gemini: Y-Koordinate von Gemini (0-1000)
        page_width_pts: Breite der PDF-Seite in Punkten
        page_height_pts: Höhe der PDF-Seite in Punkten
    
    Returns:
        (x_pdf, y_pdf) in PDF-Punkten
    """
    x_pdf = (x_gemini / 1000.0) * page_width_pts
    y_pdf = (y_gemini / 1000.0) * page_height_pts
    
    return x_pdf, y_pdf


def pdf_to_gemini(
    x_pdf: float, 
    y_pdf: float, 
    page_width_pts: float, 
    page_height_pts: float
) -> tuple[float, float]:
    """
    Konvertiert PDF-Punkte zu Gemini-Koordinaten (0-1000).
    
    Dies ist die Umkehrung von gemini_to_pdf.
    
    Args:
        x_pdf: X-Koordinate in PDF-Punkten
        y_pdf: Y-Koordinate in PDF-Punkten
        page_width_pts: Breite der PDF-Seite in Punkten
        page_height_pts: Höhe der PDF-Seite in Punkten
    
    Returns:
        (x_gemini, y_gemini) im Bereich 0-1000
    """
    x_gemini = (x_pdf / page_width_pts) * 1000.0
    y_gemini = (y_pdf / page_height_pts) * 1000.0
    
    return x_gemini, y_gemini


def gemini_bbox_to_pdf(
    bbox: dict, 
    page_width_pts: float, 
    page_height_pts: float
) -> dict:
    """
    Konvertiert eine komplette Bounding Box von Gemini zu PDF.
    
    Args:
        bbox: Dict mit x0, y0, x1, y1 (Gemini-Koordinaten 0-1000)
        page_width_pts: Breite der PDF-Seite in Punkten
        page_height_pts: Höhe der PDF-Seite in Punkten
    
    Returns:
        Dict mit x0, y0, x1, y1 in PDF-Punkten + page
    """
    x0, y0 = gemini_to_pdf(bbox.get("x0", 0), bbox.get("y0", 0), page_width_pts, page_height_pts)
    x1, y1 = gemini_to_pdf(bbox.get("x1", 0), bbox.get("y1", 0), page_width_pts, page_height_pts)
    
    return {
        "page": bbox.get("page", 0),
        "x0": round(x0, 2),
        "y0": round(y0, 2),
        "x1": round(x1, 2),
        "y1": round(y1, 2)
    }


def get_pdf_page_dimensions(pdf_bytes: bytes, page_num: int = 0) -> tuple[float, float]:
    """
    Gibt die Dimensionen einer PDF-Seite zurück.
    
    Args:
        pdf_bytes: Das PDF als Bytes
        page_num: Seitennummer (0-basiert)
    
    Returns:
        (width, height) in PDF-Punkten
    """
    import fitz  # PyMuPDF
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page_num >= len(doc):
        page_num = 0
    
    page = doc[page_num]
    rect = page.rect
    doc.close()
    
    return rect.width, rect.height
