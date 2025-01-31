# single_file_dev01/single_file/plugins/json_output.py

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from single_file.core import OutputPlugin
from single_file.utils import format_path_for_output

class JSONOutputPlugin(OutputPlugin):
    """
    Generates a comprehensive JSON representation of the codebase.
    Supports custom metadata through command line arguments.
    """
    format_name = "json"
    supported_extensions = [".json"]
    description = "Generates a JSON representation of the codebase."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add JSON-specific command line arguments."""
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
            nargs="+",
            metavar="KEY=VALUE",
            help="Add custom metadata as key=value pairs (e.g., --json-metadata version=1.0 author='John Doe')",
        )

    def generate_output(self, output_path: Path) -> None:
        """Generate JSON output according to configured options."""
        data = {
            "metadata": self._build_metadata(),
            "files": self._build_files_data(),
            "statistics": self._build_statistics()
        }

        # Only include tree if not disabled
        if not getattr(self.args, "json_no_tree", False):
            data["structure"] = self._build_directory_tree()

        # Write output with appropriate formatting
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(
                    data,
                    f,
                    indent=None if getattr(self.args, "json_compact", False) else 2,
                    default=str  # Handle non-serializable types
                )
        except Exception as e:
            self.analyzer.logger.error(f"Failed to generate JSON output: {e}")
            raise

    def _build_metadata(self) -> Dict[str, Any]:
        """Build metadata including any custom metadata from command line."""
        metadata = {
            "generated_at": datetime.now().isoformat(),
            "tool_version": "1.0.0",
            "command_args": vars(self.args),
            "analyzed_paths": [str(p) for p in self.args.paths],
        }

        # Add custom metadata from command line arguments
        if hasattr(self.args, "json_metadata") and self.args.json_metadata:
            custom_metadata = {}
            for item in self.args.json_metadata:
                try:
                    key, value = item.split("=", 1)
                    # Try to detect and convert number types
                    try:
                        if "." in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        # If conversion fails, treat as string
                        # Remove surrounding quotes if present
                        value = value.strip("'\"")
                    custom_metadata[key.strip()] = value
                except ValueError:
                    self.analyzer.logger.warning(f"Skipping invalid metadata format: {item}")
            metadata["custom"] = custom_metadata

        return metadata

    def _build_files_data(self) -> List[Dict[str, Any]]:
        """Build detailed entries for each file."""
        files_data = []

        for file_info in self.analyzer.file_info_cache.values():
            full_path = file_info["path"]
            path_obj = Path(format_path_for_output(
                full_path.parent, self.args.paths[0], self.args.absolute_paths
            ))
            file_entry = {
                "path": str(path_obj),
                "name": full_path.name,
                "bytes": file_info["size"],
                "modified": file_info["modified"].isoformat(),
                "extension": file_info["extension"],
                "is_binary": file_info["is_binary"],
                "hash": file_info.get("hash", None),
            }

            # Include content only if not disabled and non-binary
            if not getattr(self.args, "json_no_content", False) and not file_info["is_binary"]:
                file_entry["content"] = file_info.get("content", "")
                file_entry["line_count"] = file_info.get("line_count", 0)

            files_data.append(file_entry)

        return sorted(files_data, key=lambda x: x["path"])

    def _build_statistics(self) -> Dict[str, Any]:
        """Build comprehensive codebase statistics."""
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
                    "path": format_path_for_output(
                        p, self.args.paths[0], self.args.absolute_paths
                    ),
                    "bytes": s,
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

    def _build_directory_tree(self) -> List[Dict[str, Any]]:
        """Build the directory tree structure."""
        def build_tree(path: Path, base_path: Path) -> Dict[str, Any]:
            tree = {
                "type": "directory",
                "name": path.name,
                "path": format_path_for_output(path, base_path, self.args.absolute_paths),
                "children": [],
            }

            try:
                for item in sorted(path.iterdir()):
                    if item.is_dir() and self.analyzer.file_collector.should_include_path(item, is_dir=True):
                        tree["children"].append(build_tree(item, base_path))
                    elif item.is_file() and self.analyzer.file_collector.should_include_path(item, is_dir=False):
                        file_info = self.analyzer.analyze_file(item)
                        if file_info:
                            path_obj = Path(format_path_for_output(
                                item.parent, base_path, self.args.absolute_paths
                            ))
                            file_entry = {
                                "type": "file",
                                "name": item.name,
                                "path": str(path_obj),
                                "bytes": file_info["size"],
                                "modified": file_info["modified"].isoformat(),
                            }
                            tree["children"].append(file_entry)
            except PermissionError:
                self.analyzer.logger.warning(f"Permission denied accessing {path}")

            return tree

        trees = []
        for scan_path in self.args.paths:
            path = Path(scan_path).resolve()
            if path.is_dir():
                trees.append(build_tree(path, path))
            else:
                if self.analyzer.file_collector.should_include_path(path, is_dir=False):
                    file_info = self.analyzer.analyze_file(path)
                    if file_info:
                        path_obj = Path(format_path_for_output(
                            path.parent, path.parent, self.args.absolute_paths
                        ))
                        file_entry = {
                            "type": "file",
                            "name": path.name,
                            "path": str(path_obj),
                            "bytes": file_info["size"],
                            # "size_human": self._format_size(file_info["size"]),
                            "modified": file_info["modified"].isoformat(),
                        }
                        trees.append(file_entry)

        return trees