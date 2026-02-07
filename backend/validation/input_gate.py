

import io
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List
from pathlib import Path

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Logging und Config
try:
    from backend.config import config as cfg
except ImportError:
    from config import config as cfg
logger = logging.getLogger("InputGate")

# === Magic Bytes für Dateityp-Erkennung ===
MAGIC_BYTES = {
    ".pdf": b"%PDF",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff", 
    ".png": b"\x89PNG\r\n\x1a\n",
}


# =============================================================================
# RESULT DATACLASS - Einzige Struktur die wir brauchen
# =============================================================================
@dataclass
class ValidationResult:
    """Ergebnis der Validierung."""
    is_valid: bool
    processed_bytes: Optional[bytes] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    removed_pages: List[int] = field(default_factory=list)
    pdf_type: str = "unknown"  # digital_born, scanned, mixed
    page_count: int = 0
    file_size_mb: float = 0.0


# =============================================================================
# INPUT GATE - Hauptklasse
# =============================================================================
class InputGate:
    """Validiert Dateien vor OCR API-Aufrufen."""
    
    def __init__(self, quarantine_dir: str = None):
        # Fallback auf ERROR-Ordner aus Config wenn kein Pfad übergeben
        if quarantine_dir is None:
            quarantine_dir = cfg.FOLDERS.get("ERROR", "98_Error_Quarantine")
        self.quarantine_dir = Path(quarantine_dir)
        self.quarantine_dir.mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
    
    def validate(self, file_bytes: bytes, filename: str, target_model: str) -> ValidationResult:
        """
        Hauptmethode: Validiert eine Datei.
        
        Args:
            file_bytes: Datei als Bytes
            filename: Dateiname
            target_model: "Mistral OCR" oder "Gemini OCR"
        """
        ext = Path(filename).suffix.lower()
        size_mb = len(file_bytes) / (1024 * 1024)
        
        logger.info(f"Validiere: {filename} ({size_mb:.2f} MB)")
        
        # 1. Health Check (Magic Bytes + Encryption)
        error = self._health_check(file_bytes, ext)
        if error:
            self._quarantine(file_bytes, filename, error)
            return ValidationResult(is_valid=False, error_message=error)
        
        # 2. PDF-spezifische Verarbeitung
        if ext == ".pdf" and PYMUPDF_AVAILABLE:
            return self._process_pdf(file_bytes, filename, target_model)
        
        # 3. Bild oder PDF ohne PyMuPDF - nur Limit-Check
        return self._check_limits(file_bytes, filename, size_mb, 1, target_model)
    
    # -------------------------------------------------------------------------
    # HEALTH CHECK - Kernfunktion #1
    # -------------------------------------------------------------------------
    def _health_check(self, file_bytes: bytes, ext: str) -> Optional[str]:
        """Prüft Magic Bytes und Verschlüsselung. Gibt Fehler zurück oder None."""
        
        # Zu klein?
        if len(file_bytes) < 100:
            return "Datei zu klein - vermutlich korrupt"
        
        # Magic Bytes prüfen
        expected = MAGIC_BYTES.get(ext)
        if expected and not file_bytes.startswith(expected):
            return f"Ungültige {ext.upper()}-Signatur"
        
        # PDF: Verschlüsselung prüfen
        if ext == ".pdf" and PYMUPDF_AVAILABLE:
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                if doc.is_encrypted:
                    doc.close()
                    return "PDF ist passwortgeschützt"
                doc.close()
            except Exception as e:
                return f"PDF nicht lesbar: {e}"
        
        return None  # Alles OK
    
    # -------------------------------------------------------------------------
    # PDF PROCESSING - Kernfunktion #2
    # -------------------------------------------------------------------------
    def _process_pdf(self, file_bytes: bytes, filename: str, target_model: str) -> ValidationResult:
        """Analysiert PDF, entfernt leere Seiten, prüft Limits."""
        
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = len(doc)
        
        # PDF-Typ erkennen (erste 5 Seiten samplen)
        pdf_type = self._detect_pdf_type(doc)
        
        # Leere Seiten entfernen
        processed_bytes, removed = self._remove_empty_pages(doc, file_bytes)
        doc.close()
        
        new_page_count = page_count - len(removed)
        
        # Fehler abfangen: PDF ist komplett leer
        if new_page_count == 0:
            error = "Datei besteht ausschließlich aus leeren Seiten"
            self._quarantine(file_bytes, filename, error)
            return ValidationResult(is_valid=False, error_message=error)
            
        new_size_mb = len(processed_bytes) / (1024 * 1024)
        
        # Limits prüfen
        result = self._check_limits(processed_bytes, filename, new_size_mb, new_page_count, target_model)
        result.pdf_type = pdf_type
        result.removed_pages = removed
        result.page_count = new_page_count
        
        if removed:
            logger.info(f"Entfernt: {len(removed)} leere Seiten")
        
        return result
    
    def _detect_pdf_type(self, doc) -> str:
        """Erkennt ob PDF gescannt oder digital erstellt wurde."""
        check_pages = min(len(doc), 5)
        text_pages = sum(1 for i in range(check_pages) if len(doc[i].get_text().strip()) > 50)
        
        if text_pages == check_pages:
            return "digital_born"
        elif text_pages == 0:
            return "scanned"
        return "mixed"
    
    def _remove_empty_pages(self, doc, original_bytes: bytes) -> tuple[bytes, List[int]]:
        """Entfernt leere Seiten aus PDF."""
        empty = []
        for i in range(len(doc)):
            page = doc[i]
            if not page.get_text().strip() and not page.get_images() and not page.get_drawings():
                empty.append(i + 1)
        
        if not empty:
            return original_bytes, []
        
        # Sicherstellen, dass nicht alle Seiten entfernt werden (PyMuPDF Fehler verhindern)
        if len(empty) == len(doc):
            return b"", empty
        
        new_doc = fitz.open()
        for i in range(len(doc)):
            if (i + 1) not in empty:
                new_doc.insert_pdf(doc, from_page=i, to_page=i)
        
        buffer = io.BytesIO()
        new_doc.save(buffer)
        new_doc.close()
        return buffer.getvalue(), empty
    
    # -------------------------------------------------------------------------
    # LIMIT CHECK - Kernfunktion #3
    # -------------------------------------------------------------------------
    def _check_limits(self, file_bytes: bytes, filename: str, size_mb: float, 
                      page_count: int, target_model: str) -> ValidationResult:
        """Prüft ob Datei innerhalb der Modell-Limits liegt."""
        
        limits = cfg.MODEL_LIMITS.get(target_model, {"max_mb": 50, "max_pages": 1000})
        warnings = []
        
        # Größen-Limit
        if size_mb > limits["max_mb"]:
            error = f"Datei zu groß: {size_mb:.1f}MB > {limits['max_mb']}MB"
            self._quarantine(file_bytes, filename, error)
            return ValidationResult(is_valid=False, error_message=error)
        
        # Seiten-Limit (falls definiert)
        if limits["max_pages"] and page_count > limits["max_pages"]:
            error = f"Zu viele Seiten: {page_count} > {limits['max_pages']}"
            self._quarantine(file_bytes, filename, error)
            return ValidationResult(is_valid=False, error_message=error)
        
        logger.info(f"VALID: {filename} -> {target_model}")
        return ValidationResult(
            is_valid=True,
            processed_bytes=file_bytes,
            file_size_mb=size_mb,
            page_count=page_count,
            warnings=warnings
        )
    
    # -------------------------------------------------------------------------
    # QUARANTINE - Kernfunktion #4
    # -------------------------------------------------------------------------
    def _quarantine(self, file_bytes: bytes, filename: str, reason: str):
        """Speichert abgelehnte Datei mit Log."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._-")
        path = self.quarantine_dir / f"{timestamp}_{safe_name}"
        
        path.write_bytes(file_bytes)
        path.with_suffix(path.suffix + ".log").write_text(
            f"Datei: {filename}\nZeit: {datetime.now()}\nGrund: {reason}\n",
            encoding="utf-8"
        )
        logger.warning(f"QUARANTÄNE: {filename} -> {reason}")
