# single_file/plugins/default_output.py
import os
import re
from pathlib import Path
from typing import TextIO
from single_file.core import OutputPlugin
from single_file.utils import format_path_for_output, should_include_path

class DefaultOutputPlugin(OutputPlugin):
    """
    The default output plugin that generates a flattened view of the codebase.
    This plugin maintains backwards compatibility with the original flatten-codebase
    tool while adding improved path handling and filtering capabilities.
    """
    # This is crucial - it tells the plugin system what format this plugin handles
    format_name = 'default'
    
    # single_file/plugins/default_output.py
    def generate_output(self, output_path: Path) -> None:
        """
        Generate the flattened codebase output, ensuring all relative paths 
        start with './' for clarity and consistency.
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            for path in self.analyzer.args.paths:
                path = Path(path)
                if path.is_dir():
                    # Get formatted path string (not Path object)
                    display_path = format_path_for_output(
                        path, 
                        path,
                        getattr(self.analyzer.args, 'absolute_paths', False)
                    )
                    
                    # Write the directory structure
                    self._write_folder_structure(path, display_path, f)
                    
                    # Write the flattened content
                    f.write(f"### {display_path} FLATTENED CONTENT ###\n")
                    for file_path in self._find_matching_files(path):
                        file_info = self.analyzer.analyze_file(file_path)
                        if file_info and not file_info['is_binary']:
                            # Get formatted path string for the file
                            file_display_path = format_path_for_output(
                                file_path,
                                path,
                                getattr(self.analyzer.args, 'absolute_paths', False)
                            )
                            f.write(f"\n### {file_display_path} BEGIN ###\n")
                            f.write(file_info['content'].rstrip())
                            f.write(f"\n### {file_display_path} END ###\n")
                    f.write(f"\n### {display_path} FLATTENED CONTENT ###\n\n")


    def _write_folder_structure(self, actual_path: Path, display_path: str, 
                            f: TextIO, level: int = 0) -> None:
        """
        Write directory structure, properly applying ignore patterns to both files and directories.
        This function creates a visual tree representation of the directory structure,
        respecting all ignore patterns consistently.
        """
        indent = '    ' * level
        
        # First check if this directory itself should be included
        if not should_include_path(self.analyzer, actual_path, is_dir=True):
            return
            
        # Write this directory's name
        name = Path(display_path).name
        f.write(f"{indent}{name}/\n")
        
        try:
            # Get all items and sort them for consistent output
            items = sorted(actual_path.iterdir())
            
            # First handle directories
            for item in items:
                if item.is_dir():
                    # Only process directories that aren't ignored
                    if should_include_path(self.analyzer,item, is_dir=True):
                        item_display = format_path_for_output(
                            item,
                            actual_path,
                            getattr(self.analyzer.args, 'absolute_paths', False)
                        )
                        self._write_folder_structure(item, item_display, f, level + 1)
            
            # Then handle files
            for item in items:
                if not item.is_dir():
                    # Only show files that aren't ignored
                    if should_include_path(self.analyzer,item, is_dir=False):
                        f.write(f"{indent}    {item.name}\n")
                        
        except PermissionError:
            f.write(f"{indent}    <permission denied>\n")

    def _find_matching_files(self, directory: Path):
        """
        Walk through the directory and yield files that match our filtering criteria.
        
        Args:
            directory: The root directory to start traversing from
        
        Yields:
            Path objects for each matching file
        """
        for root, dirs, files in os.walk(str(directory)):
            root_path = Path(root)
            
            # Filter directories in-place
            dirs[:] = [d for d in dirs 
                      if should_include_path(self.analyzer, root_path / d, is_dir=True)]
            
            # Yield matching files
            for filename in files:
                file_path = root_path / filename
                if should_include_path(self.analyzer, file_path):
                    yield file_path

