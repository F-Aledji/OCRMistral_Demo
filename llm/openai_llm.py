import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from llm.base_llm import BaseLLM

load_dotenv()

class OpenAILLM(BaseLLM):
    def __init__(self, project_root):
        super().__init__(project_root)
        self.client = OpenAI()
        self.model = "gpt-5.1" # Wie im Original
        self.system_instructions = ""

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
                print("OpenAI Warning: Empty content received")
                return {}
                
            return json.loads(content)
        except Exception as e:
            print(f"OpenAI Error: {e}")
            return {}
