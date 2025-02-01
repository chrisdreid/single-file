# single_file/plugins/outputs/markdown_output.py

import argparse
from datetime import datetime
from pathlib import Path
import re

from single_file.core import OutputPlugin

class MarkdownOutputPlugin(OutputPlugin):
    """
    Flattens the entire codebase into a single Markdown document, ideal for LLM ingestion.
    
    It:
      - Provides a clear directory structure section, fully flattened with code blocks.
      - Includes optional codebase statistics (md_stats).
      - Inserts optional collapsible sections (md_collapsible) for file contents.
      - Uses a well-labeled BEGIN/END format for each file.
      - Automatically displays any metadata present in 'file_info' (including plugin-added fields).
      - Optionally inserts a table of contents (md_toc) linking to each file anchor.
    """
    format_name = "markdown"
    supported_extensions = [".md"]
    description = "Comprehensive Markdown flattening for LLM-friendly code ingestion."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """
        Register plugin-specific command-line arguments without changing the core.
        """
        group = parser.add_argument_group("Markdown output options")
        group.add_argument("--md-toc", action="store_true", help="Include a table of contents with links to files")
        group.add_argument("--md-stats", action="store_true", help="Include overall codebase statistics")
        group.add_argument("--md-collapsible", action="store_true", help="Wrap file content in <details> tags")
        group.add_argument("--md-full", action="store_true", help="Include the full file content (default: True for a flatten)")

    def generate_output(self, output_path: Path) -> None:
        """
        Generate a flattened Markdown representation of the codebase.
        """
        lines = []
        now = datetime.now()

        # 1) Document Header & Tool Metadata
        lines.append("# Flattened Codebase for LLM Ingestion")
        lines.append(f"_Generated on {now.strftime('%Y-%m-%d %H:%M:%S')}_")
        lines.append("")

        tool_meta = self._get_tool_metadata()
        lines.append("## Tool Metadata")
        for k, v in tool_meta.items():
            lines.append(f"- **{k}:** {v}")
        lines.append("")

        # 2) Optional Stats
        if getattr(self.args, "md_stats", False):
            stats = self.analyzer.stats
            lines.append("## Codebase Statistics")
            lines.append(f"- **Total Files:** {stats.get('total_files', 0)}")
            total_size = stats.get("total_size", 0)
            size_hr = self.filesize_human_readable(total_size)
            lines.append(f"- **Total Size:** {size_hr}")

            exts = stats.get("extensions", {})
            if exts:
                lines.append("- **Extensions Distribution:**")
                for ext, count in exts.items():
                    label = ext if ext else "[no extension]"
                    lines.append(f"  - {label}: {count}")
            lines.append("")

        # 3) Directory Structure (code block for clarity)
        lines.append("## Directory Structure")
        lines.append("```")
        lines.append(self._render_tree(self.analyzer.file_tree))
        lines.append("```")
        lines.append("")

        # 4) Prepare optional flags & file anchor references
        md_collapsible = getattr(self.args, "md_collapsible", False)
        # Typically in a "flatten" scenario, you want full content, but let the user override.
        md_full = getattr(self.args, "md_full", True)
        md_toc = getattr(self.args, "md_toc", False)

        # We collect file anchors for the TOC if needed:
        toc_entries = []

        # 5) Flattened File Contents
        lines.append("## Flattened File Contents")
        lines.append("")
        # Sort the file paths for consistent ordering.
        sorted_paths = sorted(self.analyzer.file_info_cache.keys(), key=lambda p: str(p))

        for file_path in sorted_paths:
            file_info = self.analyzer.file_info_cache[file_path]
            # The 'filepath' key might be present or removed, but it's typically the main ID for the file.
            filepath = file_info.get("filepath", "UNKNOWN_FILEPATH")
            # Generate a file-based anchor for optional TOC
            anchor = self._make_anchor(filepath)
            if md_toc:
                toc_entries.append((filepath, anchor))

            # 5A) Begin marker
            lines.append(f"### {filepath} BEGIN ### <a name=\"{anchor}\"></a>")
            
            # 5B) Show any metadata that remains in 'file_info' except 'content'
            # Because metadata_add/remove might have pruned or added keys,
            # we simply iterate what's *actually* here.
            metadata_lines = []
            for k, v in file_info.items():
                if k in ("content",):  # skip file contents in this pass
                    continue
                if hasattr(v, "strftime"):
                    # e.g. modified date
                    v = v.strftime("%Y-%m-%d %H:%M:%S")
                metadata_lines.append(f"- **{k}**: {v}")
            if metadata_lines:
                lines.append("**Metadata:**")
                lines.extend(metadata_lines)
                lines.append("")

            # 5C) If md_full => Show the file content
            if md_full:
                content = file_info.get("content", "")
                # We'll attempt to use the file extension for syntax highlighting
                code_lang = file_info.get("extension", "")
                code_block = [f"```{code_lang}", content.rstrip(), "```"]

                if md_collapsible:
                    lines.append("<details>")
                    lines.append("<summary>Show File Content</summary>")
                    lines.extend(code_block)
                    lines.append("</details>")
                else:
                    lines.extend(code_block)
            
            # 5D) End marker
            lines.append(f"### {filepath} END ###")
            lines.append("")

        # 6) If md_toc => Insert a Table of Contents linking to each file anchor
        # We'll inject that after the stats & dir structure sections.
        if md_toc and toc_entries:
            toc_lines = ["## Table of Contents"]
            for text, anchor in toc_entries:
                toc_lines.append(f"- [{text}](#{anchor})")
            # We can place it near the top (just after the codebase stats).
            # Let's say we place it right before "## Directory Structure."
            # So we find that heading and insert the TOC above it if we want.
            # For simplicity, just append after the "Tool Metadata" and "Stats" sections.
            insertion_index = None
            for i, line in enumerate(lines):
                if line.strip().startswith("## Directory Structure"):
                    insertion_index = i
                    break
            if insertion_index is not None:
                lines = lines[:insertion_index] + toc_lines + [""] + lines[insertion_index:]
            else:
                # If we didn't find the heading for some reason, just append at the end
                lines.extend(toc_lines)

        # 7) Write final Markdown file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        self.analyzer.logger.info(f"Markdown output generated at {output_path}")

    # -------------------------------------
    # HELPER METHODS
    # -------------------------------------

    def _render_tree(self, node: dict, indent: int = 0) -> str:
        """
        Recursively render the file tree in plain text form inside a code block.
        If 'type' is missing from metadata, we fallback to checking 'children'.
        """
        spacer = "    " * indent

        # If it's a directory...
        if node.get("type") == "directory" or "children" in node:
            name = node.get("dirpath", node.get("filepath", ""))
            result = f"{spacer}{name}/\n"
            for child in node.get("children", []):
                result += self._render_tree(child, indent + 1)
        else:
            # Otherwise, treat as file
            name = node.get("filepath", "")
            result = f"{spacer}{name}\n"

        return result

    def _make_anchor(self, text: str) -> str:
        """
        Create a stable anchor from a filepath by replacing non-alphanumeric characters with '-'.
        """
        anchor = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
        return anchor
