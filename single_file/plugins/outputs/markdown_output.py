# single_file_dev01/single_file/plugins/outputs/markdown_output.py

import argparse
from datetime import datetime
from pathlib import Path
from typing import TextIO, Dict, Any

from single_file.core import OutputPlugin
from single_file.utils import format_path_for_output

class MarkdownOutputPlugin(OutputPlugin):
    """
    Generates Markdown documentation of the codebase, including:
      - Directory structure
      - Flattened file contents
      - Optional table of contents, statistics, syntax highlighting
      - MD5 hashes if present (i.e. if --metadata-add md5 was used)
    """
    format_name = "markdown"
    supported_extensions = [".md"]
    description = "Generates Markdown documentation of the codebase."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        group = parser.add_argument_group("Markdown output options")
        group.add_argument(
            "--md-toc",
            action="store_true",
            help="Include a table of contents in the Markdown output.",
        )
        group.add_argument(
            "--md-stats",
            action="store_true",
            help="Include codebase statistics in the Markdown output.",
        )
        group.add_argument(
            "--md-syntax",
            action="store_true",
            help="Add syntax highlighting code fences to file contents.",
        )

    def generate_output(self, output_path: Path) -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            # Header
            self._write_header(f)

            # Optional Table of Contents
            if getattr(self.args, "md_toc", False):
                self._write_toc(f)

            # Optional Stats
            if getattr(self.args, "md_stats", False):
                self._write_statistics(f)

            # Directory structure (mirrors the approach from default_output)
            f.write("## Directory Structure\n\n")
            for path in self.args.paths:
                path_obj = Path(path).resolve()
                display_path = self._relative_display(path_obj)
                self._write_folder_structure(path_obj, display_path, f)
                f.write("\n")

            # Flattened content
            f.write("## Flattened File Contents\n\n")
            for path in self.args.paths:
                path_obj = Path(path).resolve()
                display_path = self._relative_display(path_obj)
                f.write(f"### {display_path} FLATTENED CONTENT\n\n")
                for file_path in self._find_matching_files(path_obj):
                    file_info = self.analyzer.analyze_file(file_path)
                    if file_info and not file_info.get("is_binary", False):
                        rel_str = self._relative_display(file_path)
                        f.write(f"#### {rel_str} BEGIN\n\n")
                        # Print optional MD5 if present
                        if "md5" in file_info:
                            f.write(f"**MD5**: `{file_info['md5']}`  \n\n")
                        # Syntax highlighting if requested
                        content = file_info.get("content", "")
                        language_hint = ""
                        if getattr(self.args, "md_syntax", False):
                            language_hint = self._get_language_hint(file_info.get("extension", ""))
                        f.write(f"```{language_hint}\n")
                        f.write(content)
                        f.write("\n```\n\n")
                        f.write(f"#### {rel_str} END\n\n")
                f.write(f"### {display_path} FLATTENED CONTENT\n\n")

    # -------------------------------------------------------------------------
    # Borrowed/Adapted Methods from default_output.py
    # -------------------------------------------------------------------------
    def _write_folder_structure(
        self, actual_path: Path, display_path: str, f: TextIO, level: int = 0
    ) -> None:
        """
        Writes out the directory structure in a tree-like format, using Markdown.
        Uses relative paths for display.
        """
        indent = "    " * level
        name = Path(display_path).name or str(display_path)
        f.write(f"{indent}- **{name}/**\n")

        try:
            items = sorted(actual_path.iterdir())
            # Directories first
            for item in items:
                if item.is_dir() and self.analyzer.file_collector.should_include_path(item, True):
                    item_display = self._relative_display(item)
                    self._write_folder_structure(item, item_display, f, level + 1)
            # Then files
            for item in items:
                if item.is_file() and self.analyzer.file_collector.should_include_path(item, False):
                    f.write(f"{indent}    - {item.name}\n")

        except PermissionError:
            f.write(f"{indent}    - <permission denied>\n")

    def _find_matching_files(self, directory: Path):
        """Use FileCollector to find all matching files in a directory."""
        yield from self.analyzer.file_collector.collect_files(directory)

    # -------------------------------------------------------------------------
    # Existing Markdown features (table of contents, stats, etc.)
    # -------------------------------------------------------------------------
    def _write_header(self, f: TextIO) -> None:
        f.write("# Codebase Documentation\n\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Analyzed Paths\n\n")
        for path in self.analyzer.args.paths:
            f.write(f"- `{path}`\n")
        f.write("\n")

    def _write_toc(self, f: TextIO) -> None:
        f.write("## Table of Contents\n\n")
        if getattr(self.args, "md_stats", False):
            f.write("1. [Statistics](#statistics)\n")
        f.write("2. [Directory Structure](#directory-structure)\n")
        f.write("3. [Flattened File Contents](#flattened-file-contents)\n\n")

    def _write_statistics(self, f: TextIO) -> None:
        stats = self.analyzer.stats
        f.write("## Statistics\n\n")

        f.write("### Overview\n\n")
        f.write(f"- **Total Files**: {stats['total_files']}\n")
        f.write(f"- **Total Size**: {self._format_size(stats['total_size'])}\n\n")

        f.write("### File Types\n\n")
        f.write("| Extension | Count |\n")
        f.write("|-----------|-------|\n")
        for ext, count in sorted(stats["extensions"].items()):
            label = ext if ext else "(no extension)"
            f.write(f"| {label} | {count} |\n")
        f.write("\n")

        f.write("### Largest Files\n\n")
        f.write("| File | Size |\n")
        f.write("|------|------|\n")
        for p, s in stats["largest_files"]:
            rel_str = self._relative_display(p)
            f.write(f"| `{rel_str}` | {self._format_size(s)} |\n")
        f.write("\n")

        f.write("### Recent Changes\n\n")
        f.write("| File | Modified |\n")
        f.write("|------|----------|\n")
        for p, m in stats["recently_modified"]:
            rel_str = self._relative_display(p)
            f.write(f"| `{rel_str}` | {m.strftime('%Y-%m-%d %H:%M:%S')} |\n")
        f.write("\n")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def _get_language_hint(extension: str) -> str:
        ext_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "cpp": "cpp",
            "c": "c",
            "cs": "csharp",
            "go": "go",
            "java": "java",
            "rb": "ruby",
            "php": "php",
            "html": "html",
            "css": "css",
            "scss": "scss",
            "sql": "sql",
            "md": "markdown",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "xml": "xml",
            "sh": "bash",
            "bash": "bash",
        }
        return ext_map.get(extension.lower(), "")

    @staticmethod
    def _format_size(size_in_bytes: int) -> str:
        size = float(size_in_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def _relative_display(self, path_obj: Path) -> str:
        """
        Return a relative path (with leading './' if applicable) unless
        --absolute-paths is in use. 
        """
        return format_path_for_output(
            path_obj,
            self.analyzer.args.paths[0],
            force_absolute=self.analyzer.args.absolute_paths,
        )
