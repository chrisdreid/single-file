import argparse
from datetime import datetime
from pathlib import Path
from single_file.core import OutputPlugin
from single_file.utils import format_path_for_output

class MarkdownOutputPlugin(OutputPlugin):
    """
    Generates Markdown documentation of the codebase.
    """
    format_name = "markdown"
    supported_extensions = [".md"]
    description = "Generates Markdown documentation of the codebase."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        group = parser.add_argument_group("Markdown output options")
        group.add_argument("--md-toc", action="store_true", help="Include a table of contents")
        group.add_argument("--md-stats", action="store_true", help="Include statistics")
        group.add_argument("--md-syntax", action="store_true", help="Add syntax highlighting to file contents")

    def generate_output(self, output_path: Path) -> None:
        tree = self.analyzer.file_tree
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Codebase Documentation\n\n")
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## File Tree\n\n")
            f.write(self._format_tree_as_markdown(tree))
            f.write("\n\n")
            if getattr(self.args, "md_stats", False):
                f.write(self._format_stats())
        self.analyzer.logger.info(f"Markdown output generated at {output_path}")

    def _format_tree_as_markdown(self, node: dict, indent: int = 0) -> str:
        spacer = "    " * indent
        if node.get("type") == "directory":
            path_str = node.get("dirpath", node.get("filepath", ""))
        else:
            path_str = node.get("filepath", "")
        md = f"{spacer}- `{path_str}`\n"
        if node.get("type") == "directory" and "children" in node:
            for child in node["children"]:
                md += self._format_tree_as_markdown(child, indent + 1)
        return md

    def _format_stats(self) -> str:
        stats = self.analyzer.stats
        md = "## Statistics\n\n"
        md += f"- **Total Files:** {stats['total_files']}\n"
        md += f"- **Total Size:** {self.filesize_human_readable(stats['total_size'])}\n\n"
        return md
