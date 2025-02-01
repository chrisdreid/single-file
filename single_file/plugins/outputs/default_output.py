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
    File metadata now uses a single 'filepath' (relative to the base) without extra flags.
    """
    format_name = "default"
    supported_extensions = [".txt"]

    def generate_output(self, out_file: Path) -> None:
        try:
            with open(out_file, "w", encoding="utf-8") as output_handle:
                # Render the directory tree using a helper method that walks the filesystem.
                tree_text = self._write_folder_structure(self.analyzer.args.paths[0])
                output_handle.write("### Directory Structure ###\n")
                output_handle.write(tree_text)
                
                output_handle.write("\n\n### Flattened File Contents ###\n")
                # Iterate over the file metadata cache.
                for file_info in self.analyzer.file_info_cache.values():
                    # Use the relative filepath for display.
                    file_display = file_info.get("filepath", "unknown")
                    output_handle.write(f"\n### {file_display} BEGIN ###\n")
                    content_text = file_info.get("content", "")
                    output_handle.write(content_text.rstrip())
                    output_handle.write(f"\n### {file_display} END ###\n")
            self.analyzer.logger.info(f"Default output generated at {out_file}")
        except Exception as error:
            self.analyzer.logger.error(f"Failed to generate default output: {error}")
            raise

    def _write_folder_structure(self, start_path: str, level: int = 0) -> str:
        """
        Recursively builds a plain-text directory tree starting from the given path.
        It uses the base directory (first entry in args.paths) to compute a relative filepath.
        """
        base = Path(self.analyzer.args.paths[0]).resolve()
        path_obj = Path(start_path).resolve()
        try:
            relative = path_obj.relative_to(base)
            display = f"./{relative}" if str(relative) != "." else "."
        except ValueError:
            display = str(path_obj)
        spacer = "    " * level
        result = f"{spacer}{display}/\n"
        try:
            for item in sorted(path_obj.iterdir(), key=lambda x: x.name):
                if item.is_dir() and self.analyzer.file_collector.should_include_path(item, is_dir=True):
                    result += self._write_folder_structure(str(item), level + 1)
                elif item.is_file() and self.analyzer.file_collector.should_include_path(item, is_dir=False):
                    try:
                        rel = item.resolve().relative_to(base)
                        file_display = f"./{rel}"
                    except ValueError:
                        file_display = str(item.resolve())
                    result += f"{spacer}    {file_display}\n"
        except PermissionError:
            result += f"{spacer}    <permission denied>\n"
        return result
