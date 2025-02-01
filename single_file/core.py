# single_file/core.py
"""
Core module for SingleFile.
This file defines:
  - BaseArguments: shared CLI arguments.
  - FileCollector: responsible for scanning directories, gathering file metadata,
    and building a raw file tree.
  - OutputPlugin: abstract base class for output plugins.
"""

from abc import ABC, abstractmethod
import argparse
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Iterator, List
import logging
import base64

from single_file.utils import read_file_with_encoding_gymnastics

logger = logging.getLogger(__name__)
DEFAULT_METADATA_FIELDS = ["filepath", "size", "modified", "extension"]


class BaseArguments:
    """Base class containing common arguments shared across all plugins."""
    def __init__(self):
        self.paths: List[Path] = []
        self.output_file: Path = Path("./output")
        self.formats: str = "default"
        self.ignore_errors: bool = False
        self.depth: int = 0
        self.absolute_paths: bool = False
        self.exclude_dirs: Optional[List[str]] = None
        self.exclude_files: Optional[List[str]] = None
        self.include_dirs: Optional[List[str]] = None
        self.include_files: Optional[List[str]] = None
        self.extensions: Optional[List[str]] = None
        self.exclude_extensions: Optional[List[str]] = None
        self.show_guide: bool = False
        self.replace_invalid_chars: bool = False
        self.metadata_add: List[str] = []
        self.metadata_remove: List[str] = []
        self.force_binary_content: bool = False
        self.query = None

    @classmethod
    def add_core_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--paths",
            nargs="*",
            default=["."],
            help="Paths to scan (files and directories are supported)"
        )
        parser.add_argument("--depth", type=int, default=0, help="How deep should we go? (0 = unlimited)")
        parser.add_argument("--output-file", default="output", help="Where should we save the results?")
        parser.add_argument("--formats", default="default", help="Comma-separated list of output formats")
        parser.add_argument("--extensions", nargs="*", help="Only include files with these extensions")
        parser.add_argument("--exclude-extensions", nargs="*", help="Exclude files with these extensions")
        parser.add_argument("--exclude-dirs", nargs="*", help="Folders to skip (regex patterns)")
        parser.add_argument("--exclude-files", nargs="*", help="Files to skip (regex patterns)")
        parser.add_argument("--include-dirs", nargs="*", help="Only include these folders (regex patterns)")
        parser.add_argument("--include-files", nargs="*", help="Only include these files (regex patterns)")
        parser.add_argument("--show-guide", action="store_true", help="Show the guide for AI assistance")
        parser.add_argument("--ignore-errors", action="store_true", help="Continue even if some files cause errors")
        parser.add_argument("--replace-invalid-chars", action="store_true", help="Replace invalid characters")
        parser.add_argument("--metadata-add", nargs="*", default=[], help="Add additional metadata fields")
        parser.add_argument("--metadata-remove", nargs="*", default=[], help="Remove default metadata fields")
        parser.add_argument("--force-binary-content", action="store_true", help="Read and base64-encode binary files")

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> "BaseArguments":
        instance = cls()
        for key, value in vars(args).items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        return instance


class FileCollector:
    """
    Centralized utility for scanning directories and gathering file metadata.
    Also builds a raw file tree as a nested dictionary.
    """
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.args = analyzer.args
        from single_file.utils import DEFAULT_IGNORE_PATTERNS
        self.default_ignore_patterns = DEFAULT_IGNORE_PATTERNS

    def should_include_path(self, path_item: Path, is_dir: bool = False) -> bool:
        patterns = self.default_ignore_patterns["directories"] if is_dir else self.default_ignore_patterns["files"]
        if is_dir and self.args.exclude_dirs:
            patterns.extend(self.args.exclude_dirs)
        elif not is_dir and self.args.exclude_files:
            patterns.extend(self.args.exclude_files)
        for pattern in patterns:
            try:
                if re.search(pattern, path_item.name):
                    logger.debug(f"Excluding {'directory' if is_dir else 'file'} '{path_item}' due to pattern '{pattern}'")
                    return False
            except re.error:
                logger.warning(f"Invalid regex pattern '{pattern}'")
        if not is_dir:
            ext_str = path_item.suffix[1:] if path_item.suffix else ""
            if self.args.extensions and ext_str not in self.args.extensions:
                return False
            if self.args.exclude_extensions and ext_str in self.args.exclude_extensions:
                return False
        if is_dir and self.args.include_dirs:
            if any(re.search(pattern, path_item.name) for pattern in self.args.include_dirs):
                return True
            return False
        if not is_dir and self.args.include_files:
            if any(re.search(pattern, path_item.name) for pattern in self.args.include_files):
                return True
            return False
        return True

    def collect_files(self, start_path: Path, current_depth: int = 0) -> Iterator[Path]:
        if start_path.is_file():
            yield start_path
            return
        try:
            if self.args.depth > 0 and current_depth >= self.args.depth:
                return
            entries = sorted(start_path.iterdir(), key=lambda x: x.name)
            for entry in entries:
                if entry.is_dir() and self.should_include_path(entry, is_dir=True):
                    yield from self.collect_files(entry, current_depth + 1)
            for entry in entries:
                if entry.is_file() and self.should_include_path(entry, is_dir=False):
                    yield entry
        except PermissionError:
            logger.warning(f"Permission denied accessing {start_path}")
        except Exception as err:
            if not self.args.ignore_errors:
                raise
            logger.warning(f"Error processing {start_path}: {err}")

    def get_file_metadata(self, file_item: Path) -> dict:
        base = Path(self.args.paths[0]).resolve()
        try:
            relative = file_item.resolve().relative_to(base)
            filepath = f"./{relative}"
        except ValueError:
            filepath = str(file_item.resolve())
        metadata = {
            "filepath": filepath,
            "size": file_item.stat().st_size,
            "modified": datetime.fromtimestamp(file_item.stat().st_mtime),
            "extension": file_item.suffix[1:] if file_item.suffix else ""
        }
        is_bin = self._is_binary(file_item)
        if is_bin:
            if self.args.force_binary_content:
                try:
                    with open(file_item, "rb") as f:
                        raw_data = f.read()
                    metadata["content"] = base64.b64encode(raw_data).decode("ascii")
                except Exception as e:
                    metadata["content"] = "**failed to read binary file**"
            else:
                metadata["content"] = "**binary file: skipped**"
        else:
            text_content = read_file_with_encoding_gymnastics(file_item)
            metadata["content"] = text_content
            metadata["line_count"] = len(text_content.splitlines())
        return metadata



    def _is_binary(self, file_item: Path) -> bool:
        try:
            with open(file_item, "rb") as f:
                return b"\0" in f.read(1024)
        except Exception as err:
            logger.warning(f"Could not determine if {file_item} is binary: {err}")
        return False

    def build_file_tree(self, start_path: Path, current_depth: int = 0) -> dict:
        base = Path(self.analyzer.args.paths[0]).resolve()
        try:
            relative = start_path.resolve().relative_to(base)
            filepath = f"./{relative}" if str(relative) != "." else "."
        except ValueError:
            filepath = str(start_path.resolve())
        node = {"filepath": filepath, "type": "directory" if start_path.is_dir() else "file"}
        if start_path.is_dir():
            node["children"] = []
            if self.args.depth > 0 and current_depth >= self.args.depth:
                return node
            try:
                for child in sorted(start_path.iterdir(), key=lambda x: x.name):
                    if child.is_dir() and self.should_include_path(child, is_dir=True):
                        node["children"].append(self.build_file_tree(child, current_depth + 1))
                    elif child.is_file() and self.should_include_path(child, is_dir=False):
                        metadata = self.analyzer.analyze_file(child)
                        file_node = {"filepath": metadata.get("filepath"), "type": "file", "metadata": metadata}
                        node["children"].append(file_node)
            except PermissionError:
                node["children"].append({"filepath": "<permission denied>", "type": "error"})
        return node


    def render_tree_plain(self, node: dict, indent: int = 0) -> str:
        """
        Recursively renders the raw file tree as plain text.
        Directories are suffixed with '/'.
        """
        spacer = "    " * indent
        result = ""
        if node.get("type") == "directory":
            result += f"{spacer}{node['name']}/\n"
            for child in node.get("children", []):
                result += self.render_tree_plain(child, indent + 1)
        else:
            result += f"{spacer}{node['name']}\n"
        return result


class OutputPlugin(ABC):
    """
    Base class for output plugins.
    Provides helper methods (such as filesize_human_readable) so that plugins
    can focus on formatting the already–gathered data.
    """
    format_name: str = None

    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.args = analyzer.args

    @abstractmethod
    def generate_output(self, output_path: Path) -> None:
        """Generate output in the plugin's format."""
        pass

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add plugin-specific arguments to the parser."""
        pass

    @staticmethod
    def filesize_human_readable(byte_count: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if byte_count < 1024:
                return f"{byte_count:.1f} {unit}"
            byte_count /= 1024
        return f"{byte_count:.1f} PB"
