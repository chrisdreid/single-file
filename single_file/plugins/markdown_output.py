# single_file_dev01/single_file/plugins/markdown_output.py

"""
Plugin that generates rich Markdown documentation of the codebase,
including navigation, statistics, and formatted code blocks.
"""

import argparse  # Ensure all necessary imports are present
from datetime import datetime
from pathlib import Path
from typing import TextIO, Dict, Any

from single_file.core import OutputPlugin
from single_file.utils import format_path_for_output


class MarkdownOutputPlugin(OutputPlugin):
    """
    Generates a Markdown documentation file of the codebase.

    This plugin can include optional sections such as a table of contents,
    file statistics, and syntax-highlighted code blocks.
    """
    format_name = "markdown"
    supported_extensions = [".md"]
    description = "Generates Markdown documentation of the codebase."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """
        Add Markdown-specific command line arguments.

        Args:
            parser: The argument parser to which we add our arguments.
        """
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
        """
        Generate comprehensive Markdown documentation of the codebase.

        Args:
            output_path: Path where the Markdown file should be written.
        """
        with open(output_path, "w", encoding="utf-8") as f:
            self._write_header(f)

            # Table of contents if requested
            if getattr(self.analyzer.args, "md_toc", False):
                self._write_toc(f)

            # Statistics if requested
            if getattr(self.analyzer.args, "md_stats", False):
                self._write_statistics(f)

            # File contents
            self._write_file_contents(f)

    def _write_header(self, f: TextIO) -> None:
        """
        Write a top-level header and some metadata about when and how this
        Markdown document was generated.
        """
        f.write("# Codebase Documentation\n\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Analyzed Paths\n\n")
        for path in self.analyzer.args.paths:
            f.write(f"- `{path}`\n")
        f.write("\n")

    def _write_toc(self, f: TextIO) -> None:
        """
        Write a table of contents with links (anchors) to each section.
        """
        f.write("## Table of Contents\n\n")

        # Add a link to the statistics section (if used)
        if getattr(self.analyzer.args, "md_stats", False):
            f.write("1. [Statistics](#statistics)\n")

        # Add a link to the files section
        f.write("2. [Files](#files)\n")

        # Then list each file individually
        idx = 3
        for file_info in sorted(
            self.analyzer.file_info_cache.values(), key=lambda x: str(x["path"])
        ):
            rel_str = self._relative_display(file_info["path"])
            anchor = self._make_anchor(rel_str)
            indent = "  " * rel_str.count("/")
            f.write(f"{indent}{idx}. [{rel_str}](#{anchor})\n")
            idx += 1

        f.write("\n")

    def _write_statistics(self, f: TextIO) -> None:
        """
        Write detailed codebase statistics gathered by the analyzer.
        """
        stats = self.analyzer.stats
        f.write("## Statistics\n\n")

        # Overall stats
        f.write("### Overview\n\n")
        f.write(f"- **Total Files**: {stats['total_files']}\n")
        f.write(f"- **Total Size**: {self._format_size(stats['total_size'])}\n\n")

        # File extensions breakdown
        f.write("### File Types\n\n")
        f.write("| Extension | Count |\n")
        f.write("|-----------|-------|\n")
        for ext, count in sorted(stats["extensions"].items()):
            label = ext if ext else "(no extension)"
            f.write(f"| {label} | {count} |\n")
        f.write("\n")

        # Largest files
        f.write("### Largest Files\n\n")
        f.write("| File | Size |\n")
        f.write("|------|------|\n")
        for p, s in stats["largest_files"]:
            rel_str = self._relative_display(p)
            f.write(f"| `{rel_str}` | {self._format_size(s)} |\n")
        f.write("\n")

        # Recently modified
        f.write("### Recent Changes\n\n")
        f.write("| File | Modified |\n")
        f.write("|------|----------|\n")
        for p, m in stats["recently_modified"]:
            rel_str = self._relative_display(p)
            f.write(
                f"| `{rel_str}` | {m.strftime('%Y-%m-%d %H:%M:%S')} |\n"
            )
        f.write("\n")

    def _write_file_contents(self, f: TextIO) -> None:
        """
        Write the contents (or a placeholder for binary files) for each file
        that the analyzer has processed and cached.
        """
        f.write("## Files\n\n")
        for file_info in sorted(
            self.analyzer.file_info_cache.values(), key=lambda x: str(x["path"])
        ):
            path_obj = file_info["path"]
            rel_str = self._relative_display(path_obj)
            anchor = self._make_anchor(rel_str)

            f.write(f"### <a id='{anchor}'></a>{rel_str}\n\n")
            f.write("**File Information:**\n\n")
            f.write(f"- **Size**: {self._format_size(file_info['size'])}\n")
            f.write(
                f"- **Modified**: {file_info['modified'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            f.write(f"- **Type**: {file_info['extension'] or '(no extension)'}\n\n")

            if file_info["is_binary"]:
                # Show a placeholder for binary files
                f.write("*Binary file contents omitted.*\n\n")
            else:
                # If md-syntax was requested, guess the language
                language_hint = ""
                if getattr(self.analyzer.args, "md_syntax", False):
                    language_hint = self._get_language_hint(file_info["extension"])
                f.write(f"```{language_hint}\n")
                f.write(file_info["content"])
                f.write("\n```\n\n")

            f.write("---\n\n")

    @staticmethod
    def _get_language_hint(extension: str) -> str:
        """
        Return a code fence language for syntax highlighting in Markdown,
        based on the file extension.
        """
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
        Return a relative path string (with leading './') or the absolute path,
        based on the `absolute_paths` flag.
        """
        return format_path_for_output(
            path_obj,
            self.analyzer.args.paths[0],
            force_absolute=self.analyzer.args.absolute_paths,
        )

    @staticmethod
    def _make_anchor(path_str: str) -> str:
        """
        Create a basic HTML anchor from a path string by replacing
        characters that might cause anchor issues.
        """
        return path_str.replace("/", "-").replace(".", "-").lower()
