import os
import importlib
import inspect
import sys
from pathlib import Path
from typing import Dict, Type
# from datetime import datetime
# import hashlib
from single_file.core import OutputPlugin, BaseArguments, FileCollector
import argparse

class CodebaseAnalyzer:
    """
    Main class for analyzing codebases and coordinating output generation.
    WARNING: This class modifies system state by loading plugins and analyzing files.
    """
    
    def __init__(self, args: BaseArguments):
        """
        Initialize the analyzer with arguments and set up necessary components.
        
        Args:
            args: BaseArguments instance containing configuration
            
        WARNING: This initialization process loads plugins and may execute plugin code.
        Ensure proper security measures when loading third-party plugins.
        """
        self.args = args
        self.file_info_cache: Dict[Path, dict] = {}
        self.plugins: Dict[str, Type[OutputPlugin]] = {}
        self.stats = {
            'total_files': 0,
            'total_size': 0,
            'extensions': {},
            'largest_files': [],
            'recently_modified': []
        }
        
        # Initialize file collector BEFORE loading plugins
        self.file_collector = FileCollector(self)
        
        # Load plugins after file collector is initialized
        self._load_plugins()

    def _load_plugins(self) -> None:
        """
        Dynamically load output plugins from the plugins directory.
        
        WARNING: This method executes code from plugin files.
        Ensure plugins come from trusted sources.
        """
        plugins_dir = Path(__file__).parent / 'plugins'
        if not plugins_dir.exists():
            print(f"Creating plugins directory at {plugins_dir}")
            plugins_dir.mkdir(parents=True, exist_ok=True)
            return

        # Add parent directory to Python path if needed
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        # Import each Python file in the plugins directory
        for plugin_file in plugins_dir.glob('*.py'):
            if plugin_file.name.startswith('_'):
                continue
                
            try:
                # Import using absolute import
                module_name = f"single_file.plugins.{plugin_file.stem}"
                module = importlib.import_module(module_name)
                
                # Find all OutputPlugin subclasses in the module
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        issubclass(obj, OutputPlugin) and 
                        obj is not OutputPlugin and 
                        obj.format_name):
                        self.plugins[obj.format_name] = obj
                        print(f"Loaded plugin for format: {obj.format_name}")
            
            except Exception as e:
                print(f"Error loading plugin {plugin_file}: {e}")

    def analyze_file(self, file_path: Path) -> dict:
        """
        Analyze a single file and cache its information.
        
        Args:
            file_path: Path to the file to analyze
            
        Returns:
            dict: File metadata and analysis results
            
        WARNING: This method reads file contents and calculates hashes.
        Ensure proper file permissions and available disk space.
        """
        if file_path in self.file_info_cache:
            return self.file_info_cache[file_path]

        try:
            metadata = self.file_collector.get_file_metadata(file_path)
            self._update_stats(metadata)
            self.file_info_cache[file_path] = metadata
            return metadata
            
        except Exception as e:
            if not self.args.skip_errors:
                raise
            print(f"Warning: Could not analyze {file_path}: {e}")
            return None

    def generate_outputs(self) -> None:
        """
        Generate all requested output formats using appropriate plugins.
        
        WARNING: This method writes files to the output directory.
        Ensure proper write permissions and available disk space.
        """
        # Get the list of requested formats
        requested_formats = self.args.formats.split(',')
        
        # Create the output directory if it doesn't exist
        output_dir = Path(self.args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate output for each requested format
        for format_name in requested_formats:
            format_name = format_name.strip().lower()
            if format_name not in self.plugins:
                print(f"Warning: No plugin found for format '{format_name}'")
                continue
                
            try:
                plugin = self.plugins[format_name](self)
                output_path = output_dir / f"codebase.{format_name}"
                plugin.generate_output(output_path)
                print(f"Generated {format_name} output at {output_path}")
            except Exception as e:
                print(f"Error generating {format_name} output: {e}")

    def _update_stats(self, file_info: dict) -> None:
        """
        Update the statistics with information from a new file.
        
        Args:
            file_info: Dictionary containing file information
        """
        self.stats['total_files'] += 1
        self.stats['total_size'] += file_info['size']
        
        ext = file_info['extension']
        self.stats['extensions'][ext] = self.stats['extensions'].get(ext, 0) + 1
        
        # Update largest files list
        self.stats['largest_files'].append((file_info['path'], file_info['size']))
        self.stats['largest_files'].sort(key=lambda x: x[1], reverse=True)
        self.stats['largest_files'] = self.stats['largest_files'][:10]
        
        # Update recently modified list
        self.stats['recently_modified'].append(
            (file_info['path'], file_info['modified'])
        )
        self.stats['recently_modified'].sort(key=lambda x: x[1], reverse=True)
        self.stats['recently_modified'] = self.stats['recently_modified'][:10]

def main():
    """
    Main entry point for the codebase analysis tool.
    """
    print("Starting codebase analyzer...")  # Debug output
    
    # Create argument parser
    parser = argparse.ArgumentParser(
        description='Analyze and document your codebase with multiple output formats'
    )
    
    print("Adding core arguments...")  # Debug output
    # Add core arguments from BaseArguments
    BaseArguments.add_core_arguments(parser)
    
    # Create dummy args and analyzer to get plugin list
    print("Creating initial analyzer for plugin loading...")  # Debug output
    dummy_args = BaseArguments()
    
    try:
        analyzer = CodebaseAnalyzer(dummy_args)
        
        # Let each plugin add its own arguments
        print(f"Found plugins: {list(analyzer.plugins.keys())}")  # Debug output
        for plugin in analyzer.plugins.values():
            plugin.add_arguments(parser)
        
        # Parse actual arguments
        print("Parsing command line arguments...")  # Debug output
        parsed_args = parser.parse_args()
        
        # Convert to BaseArguments instance
        args = BaseArguments.from_namespace(parsed_args)
        
        # Create and run the analyzer with the real arguments
        print("Creating analyzer with parsed arguments...")  # Debug output
        analyzer = CodebaseAnalyzer(args)
        
        print("Generating outputs...")  # Debug output
        analyzer.generate_outputs()
        
        print("Analysis complete.")  # Debug output
        
    except Exception as e:
        print(f"Error during execution: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()