from abc import ABC, abstractmethod
import os

class BaseOCR(ABC):
    """
    Abstract Base Class for OCR Engines.
    """
    def __init__(self):
        pass

    @abstractmethod
    def process_pdf(self, file_bytes, stream=False):
        """
        Process a PDF file (bytes).
        Should return an object that contains the extracted text (usually Markdown).
        """
        pass

    @abstractmethod
    def process_image(self, file_bytes, stream=False):
        """
        Process an image file (bytes).
        Should return an object that contains the extracted text.
        """
        pass

    def encode_bytes_to_base64(self, file_bytes):
        """Helper to encode bytes to base64 string"""
        import base64
        return base64.b64encode(file_bytes).decode('utf-8')
