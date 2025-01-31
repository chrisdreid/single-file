# single_file/core.py
from abc import ABC, abstractmethod
import argparse
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Iterator
from single_file.utils import read_file_with_encoding_gymnastics
from single_file import utils

class BaseArguments:
    """Base class containing common arguments shared across all plugins."""
    def __init__(self):
        self.paths: list[Path] = []
        self.output_dir: Path = Path('./output')
        self.formats: str = 'default'
        self.skip_errors: bool = False
        self.depth: int = 0
        self.absolute_paths: bool = False
        self.pattern_ignore_directories: Optional[list[str]] = None
        self.pattern_only_directories: Optional[list[str]] = None
        self.pattern_ignore_files: Optional[list[str]] = None
        self.pattern_only_files: Optional[list[str]] = None
        self.ext_only: Optional[list[str]] = None
        self.ext_ignore: Optional[list[str]] = None

    @classmethod
    def add_core_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add core arguments to the parser."""
        # ... (previous argument setup code remains the same)

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> 'BaseArguments':
        """Create a BaseArguments instance from an argparse Namespace."""
        instance = cls()
        for key, value in vars(args).items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        return instance

class FileCollector:
    """Centralized utility for consistent file collection and filtering."""
    def __init__(self, analyzer: utils.CODEBASE_ANALYZER):
        self.analyzer = analyzer
        self.args = analyzer.args
        
        # Default patterns that should always be ignored
        self.default_ignore_patterns = utils.DEFAULT_IGNORE_PATTERNS

    def should_include_path(self, path: Path, is_dir: bool = False) -> bool:
        """Determine if a path should be included based on configured patterns."""
        patterns = (self.default_ignore_patterns['directories'] if is_dir 
                   else self.default_ignore_patterns['files'])
        
        if is_dir and self.args.pattern_ignore_directories:
            patterns.extend(self.args.pattern_ignore_directories)
        elif not is_dir and self.args.pattern_ignore_files:
            patterns.extend(self.args.pattern_ignore_files)

        for pattern in patterns:
            try:
                if re.search(pattern, str(path.name)):
                    return False
            except re.error:
                print(f"Warning: Invalid regex pattern '{pattern}'")
                
        if not is_dir:
            ext = path.suffix[1:] if path.suffix else ""
            if self.args.ext_only and ext not in self.args.ext_only:
                return False
            if self.args.ext_ignore and ext in self.args.ext_ignore:
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
            print(f"Warning: Permission denied accessing {root_path}")
        except Exception as e:
            if not self.args.skip_errors:
                raise
            print(f"Warning: Error processing {root_path}: {e}")

class OutputPlugin(ABC):
    """Base class for output plugins."""
    format_name: str = None
    
    def __init__(self, analyzer: utils.CODEBASE_ANALYZER):
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
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytesize < 1024:
                return f"{bytesize:.1f} {unit}"
            bytesize /= 1024
        return f"{bytesize:.1f} PB"