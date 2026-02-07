"""
Gemeinsame Hilfsfunktionen für Schema-Operationen.
"""

from typing import Dict, Any


def clean_json_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bereinigt ein JSON-Schema für die Verwendung mit Gemini/Vertex AI.
    
    Entfernt '$schema'-Key, da dieser bei manchen API-Versionen Probleme verursacht.
    
    Args:
        schema: Das ursprüngliche JSON-Schema
        
    Returns:
        Bereinigtes Schema ohne '$schema' Key
    """
    cleaned = schema.copy()
    if '$schema' in cleaned:
        del cleaned['$schema']
    return cleaned
