# =============================================================================
# SERVICE: PRE-SCAN (Fast-Pass)
# =============================================================================
# Dieser Service nutzt PyMuPDF (fitz), um *vor* der teuren KI-Extraktion
# wichtige Metadaten wie die BA-Nummer zu finden.
#
# Ziele:
# 1. Schnell (kein LLM Call)
# 2. Robust (regex-basiert)
# 3. Ermöglicht Template-Lookup für bessere OCR-Ergebnisse
# =============================================================================

import logging
import re
import fitz  # PyMuPDF
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

class PreScanService:
    """
    Service für die schnelle Vorab-Analyse von Dokumenten.
    Nutzt PyMuPDF für Text-Extraktion.
    """
    
    # Regex für BA-Nummern: Beginnt mit 45, gefolgt von 8 Ziffern (Total 10)
    # Wortgrenzen (\b) verhindern Matches mitten in längeren Zahlen
    BA_NUMBER_PATTERN = re.compile(r"\b45\d{8}\b")
    
    def __init__(self):
        pass

    def scan_for_ba_number(self, file_bytes: bytes, filename: str, max_pages: int = 2) -> Optional[str]:
        """
        Versucht eine BA-Nummer im Dokument zu finden.
        
        Args:
            file_bytes: Der Dateiinhalt als Bytes
            filename: Dateiname (nur für Checks/Logging)
            max_pages: Wie viele Seiten sollen geprüft werden? (Default: 2)
            
        Returns:
            Gefundene BA-Nummer (str) oder None
        """
        # Nur PDFs unterstützen wir hier zuverlässig mit fitz
        if not filename.lower().endswith(".pdf"):
            logger.debug(f"PreScan übersprungen für Nicht-PDF: {filename}")
            return None
            
        try:
            # Dokument aus Memory öffnen
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            
            # Seiten durchsuchen
            for i in range(min(len(doc), max_pages)):
                page = doc[i]
                text = page.get_text()
                
                # Regex Suche
                match = self.BA_NUMBER_PATTERN.search(text)
                if match:
                    ba_number = match.group(0)
                    logger.info(f"PreScan: BA-Nummer {ba_number} auf Seite {i+1} gefunden.")
                    return ba_number
                    
            return None
            
        except Exception as e:
            logger.warning(f"Fehler im PreScan für {filename}: {e}")
            return None
            
    def extract_text_preview(self, file_bytes: bytes, max_chars: int = 1000) -> str:
        """
        Extrahiert einen Text-Ausschnitt (z.B. für Logs oder Debugging).
        """
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
                if len(text) > max_chars:
                    break
            return text[:max_chars]
        except:
            return ""

# Singleton Instanz
_prescan_service = PreScanService()

def get_prescan_service():
    return _prescan_service
