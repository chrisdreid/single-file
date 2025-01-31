# single_file_dev01/single_file/plugins/outputs/default_output.py

import logging
from pathlib import Path
from typing import TextIO
from single_file.core import OutputPlugin
from single_file.utils import format_path_for_output

logger = logging.getLogger(__name__)

class DefaultOutputPlugin(OutputPlugin):
    """
    The default output plugin that generates a flattened view of the codebase.
    """
    format_name = "default"
    supported_extensions = [".txt"]

    def generate_output(self, output_path: Path) -> None:
        """
        Generate the flattened codebase output with consistent path handling.
        """
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for path in self.args.paths:
                    path_obj = Path(path).resolve()
                    if path_obj.is_dir():
                        display_path = format_path_for_output(
                            path_obj, path_obj, self.args.absolute_paths
                        )

                        # Write the directory structure
                        self._write_folder_structure(path_obj, display_path, f)

                        # Write the flattened content
                        f.write(f"\n### {display_path} FLATTENED CONTENT ###\n")
                        for file_path in self._find_matching_files(path_obj):
                            file_info = self.analyzer.analyze_file(file_path)
                            if file_info and not file_info.get("is_binary", False):
                                file_display_path = format_path_for_output(
                                    file_path, path_obj, self.args.absolute_paths
                                )
                                f.write(f"\n### {file_display_path} BEGIN ###\n")
                                content = file_info.get("content", "")
                                f.write(content.rstrip())
                                f.write(f"\n### {file_display_path} END ###\n")
                        f.write(f"\n### {display_path} FLATTENED CONTENT ###\n\n")
            logger.info(f"Default output generated at {output_path}")
        except Exception as e:
            logger.error(f"Failed to generate default output: {e}")
            raise

    def _write_folder_structure(
        self, actual_path: Path, display_path: str, f: TextIO, level: int = 0
    ) -> None:
        """
        Write directory structure, applying consistent filtering rules.
        """
        indent = "    " * level

        # if it's the top-level directory
        name = Path(display_path).name
        f.write(f"{indent}{name}/\n")

        try:
            items = sorted(actual_path.iterdir())

            # Directories
            for item in items:
                if item.is_dir() and self.analyzer.file_collector.should_include_path(item, is_dir=True):
                    item_display = format_path_for_output(
                        item, actual_path, self.args.absolute_paths
                    )
                    self._write_folder_structure(item, item_display, f, level + 1)

            # Files
            for item in items:
                if item.is_file() and self.analyzer.file_collector.should_include_path(item, is_dir=False):
                    f.write(f"{indent}    {item.name}\n")

        except PermissionError:
            f.write(f"{indent}    <permission denied>\n")

    def _find_matching_files(self, directory: Path):
        """
        Use the centralized FileCollector to find matching files.
        """
        yield from self.analyzer.file_collector.collect_files(directory)
