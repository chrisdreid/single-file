import hashlib
import logging
import os
from single_file.plugins.metadata.plugin_base import MetadataPlugin

logger = logging.getLogger(__name__)

class MD5MetadataPlugin(MetadataPlugin):
    metadata_name = "md5"
    default = False  # Not enabled by default.
    description = "MD5 hash of the file."

    def attach_metadata(self, file_info: dict) -> None:
        # Compute MD5 from the absolute path.
        base = os.path.abspath(self.analyzer.args.paths[0]) if self.analyzer and self.analyzer.args.paths else "."
        rel_filepath = file_info.get("filepath", "")
        if rel_filepath.startswith("./"):
            rel_filepath = rel_filepath[2:]
        abs_path = os.path.join(base, rel_filepath)
        try:
            with open(abs_path, "rb") as f:
                hash_md5 = hashlib.md5()
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            file_info["md5"] = hash_md5.hexdigest()
        except Exception as e:
            logger.warning(f"Could not compute MD5 for {abs_path}: {e}")
