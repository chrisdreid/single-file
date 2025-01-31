# single_file_dev01/single_file/core.py

from abc import ABC, abstractmethod
import argparse
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Iterator, List
from single_file.utils import read_file_with_encoding_gymnastics
from single_file import utils

import logging

logger = logging.getLogger(__name__)


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

    @classmethod
    def add_core_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add core arguments to the parser."""
        parser.add_argument(
            "--paths",
            nargs="*",
            default=["."],
            help="Paths to scan",
        )
        parser.add_argument(
            "--depth",
            type=int,
            default=0,
            help="How deep should we go? (0 = all the way down!)",
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

        # Default patterns that should always be ignored
        self.default_ignore_patterns = utils.DEFAULT_IGNORE_PATTERNS

    def should_include_path(self, path: Path, is_dir: bool = False) -> bool:
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
                if re.search(pattern, str(path.name)):
                    logger.debug(
                        f"Excluding {'directory' if is_dir else 'file'} '{path}' due to pattern '{pattern}'"
                    )
                    return False
            except re.error:
                logger.warning(f"Invalid regex pattern '{pattern}'")

        if not is_dir:
            ext = path.suffix[1:] if path.suffix else ""
            if self.args.extensions and ext not in self.args.extensions:
                logger.debug(
                    f"Excluding file '{path}' due to extension '{ext}' not in extensions"
                )
                return False
            if self.args.exclude_extensions and ext in self.args.exclude_extensions:
                logger.debug(
                    f"Excluding file '{path}' due to extension '{ext}' in exclude_extensions"
                )
                return False

        if is_dir and self.args.include_dirs:
            # If include_dirs is specified, include only directories matching the patterns
            for pattern in self.args.include_dirs:
                if re.search(pattern, str(path.name)):
                    return True
            logger.debug(
                f"Excluding directory '{path}' as it does not match include_dirs patterns"
            )
            return False

        if not is_dir and self.args.include_files:
            # If include_files is specified, include only files matching the patterns
            for pattern in self.args.include_files:
                if re.search(pattern, str(path.name)):
                    return True
            logger.debug(
                f"Excluding file '{path}' as it does not match include_files patterns"
            )
            return False

        return True

    def collect_files(self, root_path: Path, current_depth: int = 0) -> Iterator[Path]:
        """Recursively collect files with consistent filtering."""
        try:
            if self.args.depth > 0 and current_depth >= self.args.depth:
                return

            items = sorted(root_path.iterdir())

            dirs = [d for d in items if d.is_dir()]
            for dir_path in dirs:
                if self.should_include_path(dir_path, is_dir=True):
                    yield from self.collect_files(dir_path, current_depth + 1)

            files = [f for f in items if f.is_file()]
            for file_path in files:
                if self.should_include_path(file_path, is_dir=False):
                    yield file_path

        except PermissionError:
            logger.warning(f"Permission denied accessing {root_path}")
        except Exception as e:
            if not self.args.ignore_errors:
                raise
            logger.warning(f"Error processing {root_path}: {e}")

    def get_file_metadata(self, file_path: Path) -> dict:
        """
        Analyze a file and gather its metadata and content.

        Args:
            file_path: Path to the file to analyze

        Returns:
            dict: A dictionary containing file metadata and content
        """
        metadata = {}
        metadata["path"] = file_path.resolve()
        metadata["size"] = file_path.stat().st_size
        metadata["modified"] = datetime.fromtimestamp(file_path.stat().st_mtime)
        metadata["extension"] = file_path.suffix[1:] if file_path.suffix else ""
        metadata["is_binary"] = self._is_binary(file_path)

        if not metadata["is_binary"] and not getattr(self.analyzer.args, 'json_no_content', False):
            metadata["content"] = read_file_with_encoding_gymnastics(file_path)
            metadata["line_count"] = len(metadata["content"].splitlines())

        # Optionally, add a hash
        metadata["hash"] = self._hash_file(file_path)

        return metadata

    def _is_binary(self, file_path: Path) -> bool:
        """
        Determine if a file is binary.

        Args:
            file_path: Path to the file to check

        Returns:
            bool: True if the file is binary, False otherwise
        """
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                if b"\0" in chunk:
                    return True
        except Exception as e:
            logger.warning(f"Could not determine if {file_path} is binary: {e}")
        return False

    def _hash_file(self, file_path: Path) -> str:
        """
        Compute the MD5 hash of a file.

        Args:
            file_path: Path to the file to hash

        Returns:
            str: MD5 hash of the file
        """
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
        except Exception as e:
            logger.warning(f"Could not compute hash for {file_path}: {e}")
            return ""
        return hash_md5.hexdigest()


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
    def _format_size(bytesize: int) -> str:
        """Convert file sizes to human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytesize < 1024:
                return f"{bytesize:.1f} {unit}"
            bytesize /= 1024
        return f"{bytesize:.1f} PB"
