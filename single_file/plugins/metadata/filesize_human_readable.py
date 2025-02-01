# single_file/plugins/metadata/size_human_readable.py

import logging
from single_file.plugins.metadata.plugin_base import MetadataPlugin
import single_file.core 

logger = logging.getLogger(__name__)

class SizeHumanReadablePlugin(MetadataPlugin):
    """
    A metadata plugin that adds a human-readable file size.
    It reads the "size" key (in bytes) from the file's metadata
    and attaches a new key "size_hr" with a formatted string.
    """
    metadata_name = "filesize_human_readable"
    default = False  # Not enabled by default.
    description = "Human-readable representation of file size."

    def attach_metadata(self, file_info: dict) -> None:
        # Only attach if "size" is present.
        if "size" in file_info:
            byte_count = file_info["size"]
            # file_info[self.metadata_name] = self.filesize_human_readable(byte_count)
            file_info[self.metadata_name] = single_file.core.OutputPlugin.filesize_human_readable(byte_count)
    
    def filesize_human_readable(self, byte_count: float) -> str:
        # Convert a byte count to a human-readable string.
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if byte_count < 1024:
                return f"{byte_count:.1f} {unit}"
            byte_count /= 1024
        return f"{byte_count:.1f} PB"
