# core.py
from abc import ABC, abstractmethod
import argparse
from pathlib import Path

class OutputPlugin(ABC):
    """
    Base class for output plugins. All output format plugins must inherit from this class
    and implement the required methods.
    """
    format_name: str = None
    
    def __init__(self, analyzer):
        self.analyzer = analyzer

    @abstractmethod
    def generate_output(self, output_path: Path) -> None:
        pass

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        pass