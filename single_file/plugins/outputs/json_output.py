# single_file_dev01/single_file/plugins/outputs/json_output.py

import argparse
import json
import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from single_file.core import OutputPlugin
from single_file.utils import format_path_for_output


class JSONOutputPlugin(OutputPlugin):
    """
    Generates a JSON representation of the codebase in a format optimized
    for default relative paths, optional binary content, and LLM ingestion.

    Example structure:

    {
      "metadata": { ... },
      "statistics": { ... },
      "codebase": [
        {
          "filepath": "./some/relative/path.py",
          "size": 123,
          "modified": "2025-01-01T12:34:56",
          "extension": "py",
          "content": "...",    # only if not --json-no-content
          "line_count": 10,    # only if text, not binary
          "md5": "...",        # only if MD5 plugin attached
          "is_binary": true,   # only if this file is actually binary
        },
        ...
      ]
    }
    """

    format_name = "json"
    supported_extensions = [".json"]
    description = "Generates a JSON representation of the codebase (relative paths, LLM-friendly)."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """
        Adds JSON-specific and binary handling CLI arguments.
        """
        group = parser.add_argument_group("JSON output options")
        group.add_argument(
            "--json-no-content",
            action="store_true",
            help="Exclude file contents from JSON output (text and binary).",
        )
        group.add_argument(
            "--json-compact",
            action="store_true",
            help="Output minified JSON (no indentation).",
        )
        group.add_argument(
            "--json-metadata",
            nargs="+",
            metavar="KEY=VALUE",
            help="Add custom metadata as key=value pairs (e.g., --json-metadata version=1.0 author='John Doe').",
        )

    def generate_output(self, output_path: Path) -> None:
        """
        Constructs a single JSON object with three top-level keys:
        - 'metadata'
        - 'statistics'
        - 'codebase' (array of file objects)
        """
        data = {
            "metadata": self._build_metadata(),
            "statistics": self._build_statistics(),
            "codebase": self._build_codebase_list(),
        }

        indent = None if getattr(self.args, "json_compact", False) else 2
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, default=str)
        except Exception as e:
            self.analyzer.logger.error(f"Failed to generate JSON output: {e}")
            raise

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------

    def _build_metadata(self) -> Dict[str, Any]:
        """
        Returns a dictionary for top-level metadata:
          - timestamp
          - tool version
          - CLI args
          - custom metadata (from --json-metadata)
          - whether or not md5 was included
        """
        from datetime import datetime

        metadata = {
            "generated_at": datetime.now().isoformat(),
            "tool_version": "1.0.0",
            "command_args": vars(self.args),
        }

        # If the user did --metadata-add md5, or if the MD5 plugin is active,
        # we can see if any file has 'md5' in its info:
        any_md5 = any("md5" in info for info in self.analyzer.file_info_cache.values())
        metadata["md5_included"] = any_md5

        # If user provided custom key=val pairs
        if hasattr(self.args, "json_metadata") and self.args.json_metadata:
            custom_metadata = {}
            for item in self.args.json_metadata:
                try:
                    key, value = item.split("=", 1)
                    # Attempt numeric conversion
                    try:
                        if "." in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        value = value.strip("'\"")
                    custom_metadata[key.strip()] = value
                except ValueError:
                    self.analyzer.logger.warning(f"Skipping invalid metadata format: {item}")
            metadata["custom"] = custom_metadata

        return metadata

    def _build_statistics(self) -> Dict[str, Any]:
        """
        Gathers analyzer statistics in a sub-dict:
          {
            "summary": {...},
            "extensions": {...},
            "largest_files": [...],
            "recent_changes": [...]
          }
        """
        stats = self.analyzer.stats
        return {
            "summary": {
                "total_files": stats["total_files"],
                "total_bytes": stats["total_size"],
            },
            "extensions": {
                ext: {
                    "count": count,
                    "extension": ext or "no extension"
                }
                for ext, count in stats["extensions"].items()
            },
            "largest_files": [
                {
                    "filepath": self._relative_file_path(p),  # use relative
                    "bytes": s,
                }
                for p, s in stats["largest_files"]
            ],
            "recent_changes": [
                {
                    "filepath": self._relative_file_path(p),  # use relative
                    "modified": m.isoformat(),
                }
                for p, m in stats["recently_modified"]
            ],
        }

    def _build_codebase_list(self) -> List[Dict[str, Any]]:
        """
        Returns a flat list of file objects, each containing metadata
        like path, size, extension, md5, etc.

        By default, path is stored relative. 
        Binary files are omitted unless --force-binary-content is set.
        """
        # Ensure everything is analyzed so file_info_cache is populated
        for p in self.args.paths:
            p_obj = Path(p).resolve()
            for fpath in self.analyzer.file_collector.collect_files(p_obj):
                self.analyzer.analyze_file(fpath)

        codebase_list = []
        for file_info in self.analyzer.file_info_cache.values():
            entry = self._build_file_entry(file_info)
            codebase_list.append(entry)

        codebase_list.sort(key=lambda x: x["filepath"])
        return codebase_list

    def _build_file_entry(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Builds a single JSON record for a file, with:
          - filepath (relative)
          - size, modified
          - extension (if present)
          - md5 (if present)
          - content if non-binary or if --force-binary-content is set
          - is_binary: true  ONLY if the file is actually binary
        """
        entry = {
            "filepath": self._relative_file_path(file_info["path"]),
            "size": file_info["size"],
            "modified": file_info["modified"].isoformat(),
        }

        # If extension wasn't removed or overwritten
        if "extension" in file_info:
            entry["extension"] = file_info["extension"]

        is_binary = file_info.get("is_binary", False)
        # Only add "is_binary": true if it is actually binary
        if is_binary:
            entry["is_binary"] = True

        # If user requested no content at all, skip content
        if getattr(self.args, "json_no_content", False):
            # do nothing else with content
            pass
        else:
            # If not binary, we can store text content
            if not is_binary:
                entry["content"] = file_info.get("content", "")
                if "line_count" in file_info:
                    entry["line_count"] = file_info["line_count"]
            else:
                # If binary & user forced binary content, store base64
                if getattr(self.args, "force_binary_content", False):
                    entry["content"] = self._base64_file(file_info["path"])

        # If MD5 is attached by the plugin
        if "md5" in file_info:
            entry["md5"] = file_info["md5"]

        return entry

    def _relative_file_path(self, path_obj: Path) -> str:
        """
        Returns a relative path (with leading './' if needed)
        relative to the first argument in --paths.
        """
        base = Path(self.args.paths[0]).resolve()
        try:
            rel = path_obj.resolve().relative_to(base)
            # if rel is '.' 
            if str(rel) == '.':
                return './'
            return f"./{rel}"
        except ValueError:
            # can't be made relative, fallback to normal
            return str(path_obj.resolve())

    def _base64_file(self, path_obj: Path) -> str:
        """
        Reads the raw bytes of a file and returns base64-encoded string.
        """
        try:
            with open(path_obj, "rb") as f:
                raw_data = f.read()
            encoded = base64.b64encode(raw_data).decode("ascii")
            return encoded
        except Exception as e:
            self.analyzer.logger.warning(f"Could not base64-encode {path_obj}: {e}")
            return ""
