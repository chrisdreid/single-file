"""
Core module for SingleFile.
This file defines the BaseArguments class, the FileCollector for scanning and filtering files,
and the base OutputPlugin interface.
"""

from abc import ABC, abstractmethod
import argparse
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Iterator, List

from single_file.utils import read_file_with_encoding_gymnastics
import logging
import base64

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
        # New: query attribute (defaults to None if not specified)
        self.query = None

    @classmethod
    def add_core_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add core arguments to the parser."""
        parser.add_argument(
            "--paths",
            nargs="*",
            default=["."],
            help="Paths to scan (files and directories are supported; if a file is given, its filters are overridden)"
        )
        parser.add_argument(
            "--depth",
            type=int,
            default=0,
            help="How deep should we go? (0 = unlimited)",
        )
        parser.add_argument(
            "--output-file",
            default="output",
            help="Where should we save the results?",
        )
        parser.add_argument(
            "--formats",
            default="default",
            help="Comma-separated list of output formats",
        )
        parser.add_argument(
            "--extensions",
            nargs="*",
            help="Only include files with these extensions (e.g., py js css)",
        )
        parser.add_argument(
            "--exclude-extensions",
            nargs="*",
            help="Exclude files with these extensions",
        )
        parser.add_argument(
            "--exclude-dirs",
            nargs="*",
            help="Folders to skip (regex patterns)",
        )
        parser.add_argument(
            "--exclude-files",
            nargs="*",
            help="Files to skip (regex patterns)",
        )
        parser.add_argument(
            "--include-dirs",
            nargs="*",
            help="Only include these folders (regex patterns)",
        )
        parser.add_argument(
            "--include-files",
            nargs="*",
            help="Only include these files (regex patterns)",
        )
        parser.add_argument(
            "--show-guide",
            action="store_true",
            help="Show the guide for AI assistance",
        )
        parser.add_argument(
            "--ignore-errors",
            action="store_true",
            help="Keep going even if some files are stubborn",
        )
        parser.add_argument(
            "--replace-invalid-chars",
            action="store_true",
            help="Replace weird characters instead of giving up",
        )
        parser.add_argument(
            "--metadata-add",
            nargs="*",
            default=[],
            help="Add one or more metadata fields (e.g., 'content', 'md5')",
        )
        parser.add_argument(
            "--metadata-remove",
            nargs="*",
            default=[],
            help="Remove one or more default metadata fields",
        )
        parser.add_argument(
            "--force-binary-content",
            action="store_true",
            help="If set, read and base64-encode binary files instead of skipping them.",
        )

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> "BaseArguments":
        """Create a BaseArguments instance from an argparse Namespace."""
        instance = cls()
        for key, value in vars(args).items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        return instance


class FileCollector:
    """Centralized utility for consistent file collection and filtering."""

    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.args = analyzer.args
        from single_file.utils import DEFAULT_IGNORE_PATTERNS
        self.default_ignore_patterns = DEFAULT_IGNORE_PATTERNS

    def should_include_path(self, path_item: Path, is_dir: bool = False) -> bool:
        """Determine if a path should be included based on configured patterns."""
        patterns = (
            self.default_ignore_patterns["directories"]
            if is_dir
            else self.default_ignore_patterns["files"]
        )

        if is_dir and self.args.exclude_dirs:
            patterns.extend(self.args.exclude_dirs)
        elif not is_dir and self.args.exclude_files:
            patterns.extend(self.args.exclude_files)

        for pattern in patterns:
            try:
                if re.search(pattern, str(path_item.name)):
                    logger.debug(
                        f"Excluding {'directory' if is_dir else 'file'} '{path_item}' due to pattern '{pattern}'"
                    )
                    return False
            except re.error:
                logger.warning(f"Invalid regex pattern '{pattern}'")

        if not is_dir:
            ext_str = path_item.suffix[1:] if path_item.suffix else ""
            if self.args.extensions and ext_str not in self.args.extensions:
                logger.debug(
                    f"Excluding file '{path_item}' because extension '{ext_str}' is not allowed"
                )
                return False
            if self.args.exclude_extensions and ext_str in self.args.exclude_extensions:
                logger.debug(
                    f"Excluding file '{path_item}' because extension '{ext_str}' is in the exclude list"
                )
                return False

        if is_dir and self.args.include_dirs:
            for pattern in self.args.include_dirs:
                if re.search(pattern, str(path_item.name)):
                    return True
            logger.debug(
                f"Excluding directory '{path_item}' as it does not match include_dirs patterns"
            )
            return False

        if not is_dir and self.args.include_files:
            for pattern in self.args.include_files:
                if re.search(pattern, str(path_item.name)):
                    return True
            logger.debug(
                f"Excluding file '{path_item}' as it does not match include_files patterns"
            )
            return False

        return True

    def collect_files(self, start_path: Path, current_depth: int = 0) -> Iterator[Path]:
        """
        Recursively collect files with filtering.
        Forced inclusion: if start_path is a file, yield it immediately (bypassing filtering).
        """
        if start_path.is_file():
            yield start_path
            return

        try:
            if self.args.depth > 0 and current_depth >= self.args.depth:
                return

            entries = sorted(start_path.iterdir())

            # Process directories
            for entry in entries:
                if entry.is_dir() and self.should_include_path(entry, is_dir=True):
                    yield from self.collect_files(entry, current_depth + 1)

            # Process files
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
        """
        Analyze a file and gather metadata.
        Forced files bypass filters except that the binary check is still applied.
        If the file is binary:
          - If --force-binary-content is flagged, read and base64-encode its content.
          - Otherwise, set content to a placeholder.
        """
        metadata = {}
        metadata["path"] = file_item.resolve()
        metadata["size"] = file_item.stat().st_size
        metadata["modified"] = datetime.fromtimestamp(file_item.stat().st_mtime)
        ext_str = file_item.suffix[1:] if file_item.suffix else ""
        metadata["extension"] = ext_str

        is_bin = self._is_binary(file_item)
        metadata["is_binary"] = is_bin

        if is_bin:
            if self.args.force_binary_content:
                try:
                    with open(file_item, "rb") as f:
                        raw_data = f.read()
                    encoded = base64.b64encode(raw_data).decode("ascii")
                    metadata["content"] = encoded
                except Exception as e:
                    metadata["content"] = "**failed to read binary data**"
            else:
                metadata["content"] = "**binary data found: skipped**"
        else:
            text_content = read_file_with_encoding_gymnastics(file_item)
            metadata["content"] = text_content
            metadata["line_count"] = len(text_content.splitlines())

        return metadata

    def _is_binary(self, file_item: Path) -> bool:
        try:
            with open(file_item, "rb") as file_handle:
                sample = file_handle.read(1024)
                return b"\0" in sample
        except Exception as err:
            logger.warning(f"Could not determine if {file_item} is binary: {err}")
        return False


class OutputPlugin(ABC):
    """Base class for output plugins."""

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
    def _format_size(byte_count: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if byte_count < 1024:
                return f"{byte_count:.1f} {unit}"
            byte_count /= 1024
        return f"{byte_count:.1f} PB"
