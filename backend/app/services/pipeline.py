# =============================================================================
# PIPELINE SERVICE (Backend-Wrapper)
# =============================================================================
# Thin-Wrapper für die UnifiedPipeline mit Backend-spezifischer Logik:
# - Annotations für Frontend (mit Koordinaten-Konvertierung)
# - Singleton-Pattern für FastAPI
# =============================================================================

import logging
from typing import Dict, Any, Optional

# Unified Pipeline importieren
# Support both: running from project root (backend.core) and from backend dir (core)
try:
    from backend.core import UnifiedPipeline, get_pipeline
except ImportError:
    from core import UnifiedPipeline, get_pipeline

# Lokale Imports für Koordinaten-Konvertierung
from . import coordinates

logger = logging.getLogger(__name__)


class PipelineService:
    """
    Backend-Wrapper für die UnifiedPipeline.
    
    Fügt Frontend-spezifische Features hinzu:
    - Annotations mit Bounding Boxes
    - Koordinaten-Konvertierung (Gemini → PDF)
    
    Beispiel:
        service = PipelineService()
        result = service.process_pdf(pdf_bytes, "rechnung.pdf")
    """
    
    def __init__(self):
        """Initialisiert den Service mit der UnifiedPipeline."""
        self.pipeline = get_pipeline()
    
    def process_pdf(self, pdf_bytes: bytes, filename: str = "document.pdf") -> Dict[str, Any]:
        """
        Verarbeitet ein PDF und gibt Backend-kompatibles Ergebnis zurück.
        
        Args:
            pdf_bytes: PDF als Bytes
            filename: Dateiname
        
        Returns:
            {
                "success": bool,
                "data": {...},
                "score": int,
                "score_cards": [...],
                "annotations": {...},
                "error": str (falls Fehler)
            }
        """
        # Pipeline aufrufen
        result = self.pipeline.process_bytes(pdf_bytes, filename, "Direct JSON")
        
        if not result.success:
            return {
                "success": False,
                "error": result.error
            }
        
        # Annotations für Frontend aufbereiten
        annotations = self._extract_annotations(result.validated_json, pdf_bytes)
        
        return {
            "success": True,
            "data": result.validated_json,
            "score": result.avg_score,
            "score_cards": result.score_cards,
            "annotations": annotations
        }
    
    def _extract_annotations(self, data: Dict[str, Any], pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Extrahiert wichtige Felder als Annotations für das Frontend.
        
        Konvertiert Gemini-Koordinaten (0-1000) zu PDF-Punkten.
        """
        annotations = {}
        
        # PDF-Dimensionen holen
        try:
            page_width, page_height = coordinates.get_pdf_page_dimensions(pdf_bytes, 0)
        except:
            page_width, page_height = 612, 792  # A4 default
        
        # Erstes Dokument verarbeiten
        docs = data.get("documents", [])
        if not docs:
            return annotations
        
        doc = docs[0].get("SupplierConfirmation", {})
        
        # BA-Nummer
        correspondence = doc.get("Correspondence", {})
        if correspondence:
            ba_num = correspondence.get("number")
            ba_bbox = correspondence.get("bbox")
            if ba_num:
                annotations["ba_number"] = {"value": ba_num}
                if ba_bbox:
                    annotations["ba_number"]["bbox"] = coordinates.gemini_bbox_to_pdf(
                        ba_bbox, page_width, page_height
                    )
        
        # Belegdatum
        scd = doc.get("supplierConfirmationData", {})
        date_obj = scd.get("date", {})
        if date_obj:
            date_val = date_obj.get("value")
            date_bbox = date_obj.get("bbox")
            if date_val:
                annotations["document_date"] = {"value": date_val}
                if date_bbox:
                    annotations["document_date"]["bbox"] = coordinates.gemini_bbox_to_pdf(
                        date_bbox, page_width, page_height
                    )
        
        # Dokumenttyp
        doc_type = scd.get("documentType")
        doc_type_bbox = scd.get("documentType_bbox")
        if doc_type:
            annotations["document_type"] = {"value": doc_type}
            if doc_type_bbox:
                annotations["document_type"]["bbox"] = coordinates.gemini_bbox_to_pdf(
                    doc_type_bbox, page_width, page_height
                )
        
        # Gesamtsumme
        total = doc.get("documentNetTotal")
        total_bbox = doc.get("documentNetTotal_bbox")
        if total:
            annotations["total_value"] = {"value": total}
            if total_bbox:
                annotations["total_value"]["bbox"] = coordinates.gemini_bbox_to_pdf(
                    total_bbox, page_width, page_height
                )
        
        # Lieferant
        supplier = doc.get("invoiceSupplierData", {}).get("SupplierPartner", {})
        if supplier:
            sup_num = supplier.get("number")
            sup_bbox = supplier.get("number_bbox")
            if sup_num:
                annotations["vendor_name"] = {"value": str(sup_num)}
                if sup_bbox:
                    annotations["vendor_name"]["bbox"] = coordinates.gemini_bbox_to_pdf(
                        sup_bbox, page_width, page_height
                    )
        
        return annotations


# =============================================================================
# SINGLETON
# =============================================================================

_pipeline_service: Optional[PipelineService] = None

def get_pipeline_service() -> PipelineService:
    """Gibt die Pipeline-Service-Instanz zurück (Singleton)."""
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = PipelineService()
    return _pipeline_service
