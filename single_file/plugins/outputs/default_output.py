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

    def generate_output(self, out_file: Path) -> None:
        try:
            with open(out_file, "w", encoding="utf-8") as output_handle:
                for input_path in self.args.paths:
                    input_path_obj = Path(input_path).resolve()
                    if input_path_obj.is_dir():
                        display_path = format_path_for_output(
                            input_path_obj, input_path_obj, self.args.absolute_paths
                        )
                        # Write the directory structure
                        self._write_folder_structure(input_path_obj, display_path, output_handle)

                        # Write the flattened content for this directory
                        output_handle.write(f"\n### {display_path} FLATTENED CONTENT ###\n")
                        for file_entry in self._find_matching_files(input_path_obj):
                            file_metadata = self.analyzer.analyze_file(file_entry)
                            if file_metadata and not file_metadata.get("is_binary", False):
                                file_display = format_path_for_output(
                                    file_entry, input_path_obj, self.args.absolute_paths
                                )
                                output_handle.write(f"\n### {file_display} BEGIN ###\n")
                                content_text = file_metadata.get("content", "")
                                output_handle.write(content_text.rstrip())
                                output_handle.write(f"\n### {file_display} END ###\n")
                        output_handle.write(f"\n### {display_path} FLATTENED CONTENT ###\n\n")
                    elif input_path_obj.is_file():
                        # Forced inclusion: process the file even if its extension would normally be filtered.
                        file_metadata = self.analyzer.analyze_file(input_path_obj)
                        file_display = format_path_for_output(
                            input_path_obj, input_path_obj.parent, self.args.absolute_paths
                        )
                        output_handle.write(f"\n### {file_display} BEGIN ###\n")
                        content_text = file_metadata.get("content", "")
                        output_handle.write(content_text.rstrip())
                        output_handle.write(f"\n### {file_display} END ###\n")
            logger.info(f"Default output generated at {out_file}")
        except Exception as error:
            logger.error(f"Failed to generate default output: {error}")
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
