# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================
# Pydantic Models für API Request Bodies
# =============================================================================

from pydantic import BaseModel
from typing import Dict, Any


class AnnotationUpdate(BaseModel):
    """Request-Body für Annotation Update."""
    fields: Dict[str, Any]


class ClaimResponse(BaseModel):
    """Response für Claim-Endpoint."""
    status: str
    user_id: str
    expires_at: str


class ProcessResponse(BaseModel):
    """Response für Process-Endpoint."""
    success: bool
    score: int | None = None
    status: str | None = None
    data: Dict[str, Any] | None = None
    annotations: Dict[str, Any] | None = None
