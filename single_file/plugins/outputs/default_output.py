import logging
from pathlib import Path
from typing import TextIO
from single_file.core import OutputPlugin
from single_file.utils import format_path_for_output

logger = logging.getLogger(__name__)

class DefaultOutputPlugin(OutputPlugin):
    """
    The default output plugin that generates a flattened view of the codebase.
    It prints a directory tree and, for each file, its content between BEGIN/END markers.
    """
    format_name = "default"
    supported_extensions = [".txt"]

    def generate_output(self, out_file: Path) -> None:
        try:
            with open(out_file, "w", encoding="utf-8") as output_handle:
                tree_text = self._render_tree(self.analyzer.file_tree)
                output_handle.write("### Directory Structure ###\n")
                output_handle.write(tree_text)
                output_handle.write("\n\n### Flattened File Contents ###\n")
                for file_info in self.analyzer.file_info_cache.values():
                    file_display = file_info.get("filepath", "unknown")
                    output_handle.write(f"\n### {file_display} BEGIN ###\n")
                    content_text = file_info.get("content", "")
                    output_handle.write(content_text.rstrip())
                    output_handle.write(f"\n### {file_display} END ###\n")
            self.analyzer.logger.info(f"Default output generated at {out_file}")
        except Exception as error:
            self.analyzer.logger.error(f"Failed to generate default output: {error}")
            raise

    def _render_tree(self, node: dict, indent: int = 0) -> str:
        spacer = "    " * indent
        # For directories, show 'dirpath'; for files, show 'filepath'.
        if node.get("type") == "directory":
            path_str = node.get("dirpath", node.get("filepath", ""))
        else:
            path_str = node.get("filepath", "")
        result = f"{spacer}{path_str}\n"
        if node.get("type") == "directory" and "children" in node:
            for child in node["children"]:
                result += self._render_tree(child, indent + 1)
        return result
