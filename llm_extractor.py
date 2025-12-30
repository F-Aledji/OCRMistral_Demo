import os
from openai import AzureOpenAI

class AzureLLM:
    """Klasse um Azure OpenAI API zu nutzen"""
    def __init__(self, AZURE_OPENAI_API_KEY, endpoint, deployment_id, api_version):
    
        self.client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            azure_endpoint=endpoint,
            deployment_id=deployment_id,
            api_version=api_version
        )

def extract_structured_data(self, text, instruction):
    system_prompt = f"Du bist ein Experten der Datenanalyse und Datenextraktion. {instruction}"

    response
