import base64
import logging
import os
from single_file.plugins.metadata.plugin_base import MetadataPlugin

logger = logging.getLogger(__name__)

class BinaryContentPlugin(MetadataPlugin):
    metadata_name = "binary_content"
    default = False  # Not enabled by default.
    description = "Base64-encoded binary content (if forced)."

    def attach_metadata(self, file_info: dict) -> None:
        # Only proceed if the current content indicates that binary data was skipped.
        if file_info.get("content") != "**binary file: skipped**":
            return
        base = os.path.abspath(self.analyzer.args.paths[0]) if self.analyzer and self.analyzer.args.paths else "."
        rel_filepath = file_info.get("filepath", "")
        if rel_filepath.startswith("./"):
            rel_filepath = rel_filepath[2:]
        abs_path = os.path.join(base, rel_filepath)
        try:
            with open(abs_path, "rb") as f:
                raw_data = f.read()
            file_info["binary_content"] = base64.b64encode(raw_data).decode("ascii")
        except Exception as e:
            logger.warning(f"Could not base64-encode {abs_path}: {e}")
