# single_file_dev01/single_file/plugins/metadata/md5_hash.py

import logging
import hashlib
from pathlib import Path
from typing import Dict, Any

from single_file.plugins.metadata.plugin_base import MetadataPlugin

logger = logging.getLogger(__name__)

class MD5MetadataPlugin(MetadataPlugin):
    """Plugin that attaches an MD5 hash to the file_info dictionary."""

    metadata_name = "md5"

    def attach_metadata(self, file_info: Dict[str, Any]) -> None:
        path_obj = file_info.get("path")
        if not path_obj:
            return
        if not file_info.get("md5") and Path(path_obj).is_file():
            file_info["md5"] = self._compute_md5(path_obj)

    def _compute_md5(self, file_path: Path) -> str:
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
        except Exception as e:
            logger.warning(f"Could not compute MD5 for {file_path}: {e}")
            return ""
        return hash_md5.hexdigest()
