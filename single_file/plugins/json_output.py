# single_file_dev01/single_file/plugins/json_output.py

"""
Plugin that generates a comprehensive JSON representation of the codebase.
Supports additional JSON-specific formatting options.
"""

import argparse  # Added import
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from single_file.core import OutputPlugin
from single_file.utils import format_path_for_output, should_include_path


class JSONOutputPlugin(OutputPlugin):
    """
    Generates a comprehensive JSON representation of the codebase.

    Supports additional JSON-specific formatting options.
    """
    format_name = "json"
    supported_extensions = [".json"]
    description = "Generates a comprehensive JSON representation of the codebase."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """
        Add JSON-specific command line arguments.

        Args:
            parser: The argument parser to which we add our arguments.
        """
        group = parser.add_argument_group("JSON output options")
        group.add_argument(
            "--json-no-content",
            action="store_true",
            help="Exclude file contents from JSON output",
        )
        group.add_argument(
            "--json-no-tree",
            action="store_true",
            help="Exclude directory tree from output",
        )
        group.add_argument(
            "--json-compact",
            action="store_true",
            help="Output minified JSON instead of pretty-printed",
        )
        group.add_argument(
            "--json-metadata",
            action="store_true",
            help="Include metadata in JSON output (default: off)",
        )

    def generate_output(self, output_path: Path) -> None:
        """
        Generate JSON output according to configured options.

        Args:
            output_path: Path where the JSON file should be written.
        """
        data: Dict[str, Any] = {}

        # Only include tree if not disabled
        if not self.args.json_no_tree:
            data["structure"] = self._build_directory_tree()

        # Always include files data
        data["files"] = self._build_files_data()

        # Include statistics
        data["statistics"] = self._build_statistics()

        # Include metadata if requested
        if self.args.json_metadata:
            data["metadata"] = {
                "generated_at": datetime.now().isoformat(),
                "tool_version": "1.0.0",  # Update as necessary
                "command_args": vars(self.args),
                "analyzed_paths": [str(p) for p in self.args.paths],
            }

        # Write output with appropriate formatting
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(
                    data,
                    f,
                    indent=None if self.args.json_compact else 2,
                    default=str,  # Handle non-serializable types
                )
            self.analyzer.logger.info(f"JSON output generated at {output_path}")
        except Exception as e:
            self.analyzer.logger.error(f"Failed to generate JSON output: {e}")
            raise

    def _build_directory_tree(self) -> List[Dict[str, Any]]:
        """
        Builds the directory tree structure.

        Returns:
            A list of dictionaries representing the directory tree.
        """

        def build_tree(path: Path, base_path: Path) -> Dict[str, Any]:
            relative_path = path.relative_to(base_path)
            tree = {
                "type": "directory",
                "name": path.name,
                "path": format_path_for_output(path, base_path, self.args.absolute_paths),
                "children": [],
            }

            try:
                for item in sorted(path.iterdir()):
                    if item.is_dir():
                        if should_include_path(self.analyzer, item, is_dir=True):
                            tree["children"].append(build_tree(item, base_path))
                    else:
                        if should_include_path(self.analyzer, item, is_dir=False):
                            file_info = self.analyzer.analyze_file(item)
                            if file_info:
                                file_entry = {
                                    "type": "file",
                                    "name": item.name,
                                    "path": format_path_for_output(
                                        item, base_path, self.args.absolute_paths
                                    ),
                                    "size": file_info["size"],
                                    "size_human": self._format_size(file_info["size"]),
                                    "modified": file_info["modified"].isoformat(),
                                }
                                tree["children"].append(file_entry)
            except PermissionError:
                self.analyzer.logger.warning(f"Permission denied accessing {path}")

            return tree

        directory_trees = []
        for scan_path in self.args.paths:
            path = Path(scan_path).resolve()
            if path.is_dir():
                directory_trees.append(build_tree(path, path))
            else:
                # If a file is provided directly
                if should_include_path(self.analyzer, path, is_dir=False):
                    file_info = self.analyzer.analyze_file(path)
                    if file_info:
                        file_entry = {
                            "type": "file",
                            "name": path.name,
                            "path": format_path_for_output(path, path.parent, self.args.absolute_paths),
                            "size": file_info["size"],
                            "size_human": self._format_size(file_info["size"]),
                            "modified": file_info["modified"].isoformat(),
                        }
                        directory_trees.append(file_entry)

        return directory_trees

    def _build_files_data(self) -> List[Dict[str, Any]]:
        """
        Builds detailed entries for each file.

        Returns:
            A list of dictionaries containing file metadata and content.
        """
        files_data = []

        for file_info in self.analyzer.file_info_cache.values():
            file_entry = {
                "path": format_path_for_output(
                    file_info["path"], self.args.paths[0], self.args.absolute_paths
                ),
                "name": file_info["path"].name,
                "size": file_info["size"],
                "size_human": self._format_size(file_info["size"]),
                "modified": file_info["modified"].isoformat(),
                "extension": file_info["extension"],
                "is_binary": file_info["is_binary"],
                "hash": file_info.get("hash", None),  # Include if available
            }

            # Include content only if not disabled and non-binary
            if not self.args.json_no_content and not file_info["is_binary"]:
                file_entry["content"] = file_info.get("content", "")
                file_entry["line_count"] = file_info.get("line_count", 0)

            files_data.append(file_entry)

        # Sort files by path for consistency
        files_data.sort(key=lambda x: x["path"])
        return files_data

    def _build_statistics(self) -> Dict[str, Any]:
        """
        Builds comprehensive codebase statistics.

        Returns:
            A dictionary containing various statistics about the codebase.
        """
        stats = self.analyzer.stats
        statistics = {
            "summary": {
                "total_files": stats["total_files"],
                "total_size": stats["total_size"],
                "total_size_human": self._format_size(stats["total_size"]),
            },
            "extensions": {
                ext: {"count": count, "extension": ext or "no extension"}
                for ext, count in stats["extensions"].items()
            },
            "largest_files": [
                {
                    "path": format_path_for_output(
                        p, self.args.paths[0], self.args.absolute_paths
                    ),
                    "size": s,
                    "size_human": self._format_size(s),
                }
                for p, s in stats["largest_files"]
            ],
            "recent_changes": [
                {
                    "path": format_path_for_output(
                        p, self.args.paths[0], self.args.absolute_paths
                    ),
                    "modified": m.isoformat(),
                }
                for p, m in stats["recently_modified"]
            ],
        }

        return statistics

    @staticmethod
    def _format_size(size_in_bytes: int) -> str:
        """
        Convert a numeric file size into a human-readable string.
        """
        size = float(size_in_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
