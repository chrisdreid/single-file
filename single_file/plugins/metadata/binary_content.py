# single_file/plugins/metadata/binary_content.py

import base64
import logging
from pathlib import Path
from typing import Dict, Any

from single_file.plugins.metadata.plugin_base import MetadataPlugin

logger = logging.getLogger(__name__)

class BinaryContentPlugin(MetadataPlugin):
    """
    Converts any file with 'content' == '**binary data found: skipped**'
    into base64-encoded content, preserving the rest.
    """

    metadata_name = "binary_content"

    def attach_metadata(self, file_info: Dict[str, Any]) -> None:
        content_val = file_info.get("content")
        if content_val != "**binary data found: skipped**":
            # It's either text or something else, do nothing
            return

        # If we get here, it's actually binary => encode it
        path_obj = file_info.get("path")
        if not path_obj:
            return

        try:
            with open(path_obj, "rb") as f:
                raw_data = f.read()
            encoded = base64.b64encode(raw_data).decode("ascii")
            file_info["content"] = encoded
        except Exception as e:
            logger.warning(f"Could not base64-encode {path_obj}: {e}")
