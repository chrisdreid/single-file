from abc import ABC, abstractmethod
from typing import Dict, Any

class MetadataPlugin(ABC):
    def __init__(self, analyzer=None):
        self.analyzer = analyzer

    @abstractmethod
    def attach_metadata(self, file_info: Dict[str, Any]) -> None:
        """Modify file_info in place by adding or changing metadata."""
        pass
