"""
Utility für das Laden von System-Prompts aus Dateien.
"""

import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Basis-Pfad zum prompts-Ordner
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


@lru_cache(maxsize=10)
def load_prompt(prompt_name: str) -> str:
    """
    Lädt einen System-Prompt aus einer .txt Datei.
    
    Args:
        prompt_name: Name der Prompt-Datei ohne .txt Extension
                    z.B. "ocr_extraction" für prompts/ocr_extraction.txt
    
    Returns:
        Der Prompt-Text als String
        
    Raises:
        FileNotFoundError: Wenn die Prompt-Datei nicht existiert
    """
    prompt_path = os.path.join(PROMPTS_DIR, f"{prompt_name}.txt")
    
    if not os.path.exists(prompt_path):
        logger.error(f"Prompt-Datei nicht gefunden: {prompt_path}")
        raise FileNotFoundError(f"Prompt '{prompt_name}' nicht gefunden in {PROMPTS_DIR}")
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read().strip()
    
    logger.debug(f"Prompt '{prompt_name}' geladen ({len(prompt)} Zeichen)")
    return prompt


def reload_prompts():
    """Leert den Prompt-Cache, um Änderungen zu übernehmen."""
    load_prompt.cache_clear()
    logger.info("Prompt-Cache geleert")
