import json
import logging
from openai import OpenAI
from llm.base_llm import BaseLLM
import config.config as cfg

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTIONS = """Du bist ein Markdown zu JSON parser. Du erhältst Markdown-Text und eine JSON-Schema Definition. Deine Aufgabe ist es, die relevanten Daten aus dem Markdown basierend des Schemas zu extrahieren und sie in einem validen JSON-Format zurückzugeben.
"""
class OpenAILLM(BaseLLM):
    def __init__(self, project_root):
        super().__init__(project_root)
        self.client = OpenAI()
        self.model = cfg.OPENAI_MODEL
        self.system_instructions = SYSTEM_INSTRUCTIONS

    def get_json_extraction(self, markdown_text, extraction_schema):
        """Ruft OpenAI API auf um strukturierte JSON-Daten aus Markdown zu extrahieren."""
        try:
            response = self.client.responses.create(
                model=self.model,
                reasoning={"effort": "medium"},
                instructions=self.system_instructions,
                input=markdown_text,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "markdown_extraction",
                        "schema": extraction_schema,
                    }
                }
            )
            
            content = response.output_text
            if not content:
                logger.warning("OpenAI: Empty content received")
                return {}
                
            return json.loads(content)
        except Exception as e:
            logger.error(f"OpenAI Error: {e}")
            return {}
