# single_file_dev01/single_file/plugins/default_output.py

import logging
from pathlib import Path
from typing import TextIO
from single_file.core import OutputPlugin
from single_file.utils import format_path_for_output, should_include_path


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

        Args:
            output_path: Path where the output file should be written
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

                        # Write the flattened content with clear section markers
                        f.write(f"\n### {display_path} FLATTENED CONTENT ###\n")
                        for file_path in self._find_matching_files(path_obj):
                            file_info = self.analyzer.analyze_file(file_path)
                            if file_info and not file_info["is_binary"]:
                                file_display_path = format_path_for_output(
                                    file_path, path_obj, self.args.absolute_paths
                                )
                                f.write(f"\n### {file_display_path} BEGIN ###\n")
                                f.write(file_info["content"].rstrip())
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

        Args:
            actual_path: The actual filesystem path
            display_path: The path to display in output
            f: Open file handle for writing
            level: Current indentation level
        """
        indent = "    " * level

        # First check if this directory itself should be included
        if not should_include_path(self.analyzer, actual_path, is_dir=True):
            return

        # Write this directory's name
        name = Path(display_path).name
        f.write(f"{indent}{name}/\n")

        try:
            # Get all items and sort them for consistent output
            items = sorted(actual_path.iterdir())

            # Handle directories first for clearer structure
            for item in items:
                if item.is_dir():
                    if should_include_path(self.analyzer, item, is_dir=True):
                        item_display = format_path_for_output(
                            item, actual_path, self.args.absolute_paths
                        )
                        self._write_folder_structure(item, item_display, f, level + 1)

            # Then handle files
            for item in items:
                if not item.is_dir():
                    if should_include_path(self.analyzer, item, is_dir=False):
                        f.write(f"{indent}    {item.name}\n")

        except PermissionError:
            f.write(f"{indent}    <permission denied>\n")

    def _find_matching_files(self, directory: Path):
        """
        Use the centralized FileCollector to find matching files.

        Args:
            directory: Root directory to start searching from

        Yields:
            Path objects for matching files
        """
        yield from self.analyzer.file_collector.collect_files(directory)
