"""
Validation Module - Input Gate, Score Engine, Judge für OCR Pipeline.
"""

from .input_gate import InputGate, ValidationResult
from .score import ScoreCard, ScoreEngine
from .judge import Judge

__all__ = ["InputGate", "ValidationResult", "ScoreCard", "ScoreEngine", "Judge"]
