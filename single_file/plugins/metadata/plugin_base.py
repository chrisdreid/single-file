# single_file_dev01/single_file/plugins/metadata/plugin_base.py

from abc import ABC, abstractmethod
from typing import Dict, Any

class MetadataPlugin(ABC):
    """
    Base class for metadata plugins. Provides a hook to modify file_info in place.
    """

    @abstractmethod
    def attach_metadata(self, file_info: Dict[str, Any]) -> None:
        """Attaches or modifies metadata in the file_info dictionary."""
        pass
