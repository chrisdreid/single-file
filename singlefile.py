# Core implementation file (codebase_analyzer.py)
import os
import argparse
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Any, Type
from abc import ABC, abstractmethod
from datetime import datetime
import hashlib
from single_file.core import OutputPlugin
from single_file.utils import read_file_with_encoding_gymnastics

class CodebaseAnalyzer:
    """
    Main class for analyzing codebases and coordinating output generation through plugins.
    This class handles file analysis, caching, and plugin management.
    """
    def __init__(self, args: argparse.Namespace):
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
        
        # Load plugins when initializing
        self._load_plugins()

    # Instead of using importlib.util, we can use regular import machinery
    def _load_plugins(self) -> None:
        """
        Dynamically load output plugins from the plugins directory.
        """
        plugins_dir = Path(__file__).parent / 'plugins'
        if not plugins_dir.exists():
            print(f"Creating plugins directory at {plugins_dir}")
            plugins_dir.mkdir(parents=True, exist_ok=True)
            return

        # Add parent directory to Python path
        import sys
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
                module = __import__(module_name, fromlist=['*'])
                
                # Find all OutputPlugin subclasses in the module
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and issubclass(obj, OutputPlugin) 
                        and obj is not OutputPlugin and obj.format_name):
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
            Dictionary containing file information and analysis results
        """
        if file_path in self.file_info_cache:
            return self.file_info_cache[file_path]

        try:
            stats = file_path.stat()
            content = None
            is_binary = self._is_likely_binary(file_path)
            
            if not is_binary:
                try:
                    content = read_file_with_encoding_gymnastics(file_path)
                except Exception as e:
                    content = f"Error reading file: {str(e)}"

            file_info = {
                'path': file_path,
                'relative_path': file_path.relative_to(self.args.paths[0]),
                'size': stats.st_size,
                'modified': datetime.fromtimestamp(stats.st_mtime),
                'extension': file_path.suffix[1:] if file_path.suffix else "none",
                'is_binary': is_binary,
                'content': content,
                'hash': self._calculate_file_hash(file_path) if not is_binary else None
            }

            # Update statistics
            self._update_stats(file_info)
            
            self.file_info_cache[file_path] = file_info
            return file_info
            
        except Exception as e:
            if not self.args.skip_errors:
                raise
            print(f"Warning: Could not analyze {file_path}: {e}")
            return None

    def generate_outputs(self) -> None:
        """
        Generate all requested output formats using the appropriate plugins.
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

    @staticmethod
    def _is_likely_binary(file_path: Path) -> bool:
        """
        Determine if a file is likely binary by examining its contents.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if the file appears to be binary, False otherwise
        """
        try:
            chunk_size = 8192
            with open(file_path, 'rb') as f:
                chunk = f.read(chunk_size)
                return b'\x00' in chunk or \
                       sum(1 for b in chunk if b > 127) > len(chunk) * 0.3
        except Exception:
            return True

    @staticmethod
    def _calculate_file_hash(file_path: Path) -> str:
        """
        Calculate a SHA-256 hash of the file's contents.
        
        Args:
            file_path: Path to the file to hash
            
        Returns:
            Hexadecimal string of the file's SHA-256 hash
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

# def main():
#     """
#     Main entry point for the codebase analysis tool.
#     """
#     parser = argparse.ArgumentParser(
#         description='Analyze and document your codebase with multiple output formats'
#     )
    
#     # Core arguments
#     parser.add_argument('paths', nargs='+', help='Paths to analyze')
#     parser.add_argument('--output-dir', default='./output',
#                        help='Directory for output files')
#     parser.add_argument('--formats', default='default',
#                        help='Comma-separated list of output formats')
#     parser.add_argument('--skip-errors', action='store_true',
#                        help='Continue on file reading errors')
#     parser.add_argument('--depth', type=int, default=0,
#                        help='Maximum directory depth (0 = unlimited)')
    
#     # Load the analyzer to get plugin list
#     dummy_args = argparse.Namespace()
#     analyzer = CodebaseAnalyzer(dummy_args)
    
#     # Let each plugin add its own arguments
#     for plugin in analyzer.plugins.values():
#         plugin.add_arguments(parser)
    
#     args = parser.parse_args()
    
#     # Create and run the analyzer with the real arguments
#     analyzer = CodebaseAnalyzer(args)
#     analyzer.generate_outputs()


def main():
    """
    Main entry point for the codebase analysis tool. This function sets up argument parsing,
    loads plugins, and orchestrates the analysis process.
    """
    parser = argparse.ArgumentParser(
        description='Analyze and document your codebase with multiple output formats'
    )
    
    # Core arguments group for better organization
    core_group = parser.add_argument_group('Core options')
    core_group.add_argument('paths', nargs='+', 
                           help='Paths to analyze')
    core_group.add_argument('--output-dir', default='./output',
                           help='Directory for output files')
    core_group.add_argument('--formats', default='default',
                           help='Comma-separated list of output formats')
    core_group.add_argument('--skip-errors', action='store_true',
                           help='Continue on file reading errors')
    core_group.add_argument('--depth', type=int, default=0,
                           help='Maximum directory depth (0 = unlimited)')

    # Filtering options group
    filter_group = parser.add_argument_group('Filtering options')
    filter_group.add_argument('--pattern_ignore_directories', nargs='+',
                             help='Regular expressions for directories to ignore')
    filter_group.add_argument('--pattern_only_directories', nargs='+',
                             help='Regular expressions for directories to include')
    filter_group.add_argument('--pattern_ignore_files', nargs='+',
                             help='Regular expressions for files to ignore')
    filter_group.add_argument('--pattern_only_files', nargs='+',
                             help='Regular expressions for files to include')
    filter_group.add_argument('--ext_only', nargs='+',
                             help='Only include files with these extensions')
    filter_group.add_argument('--ext_ignore', nargs='+',
                             help='Ignore files with these extensions')
    core_group.add_argument('--absolute-paths', action='store_true',
                         help='Use absolute paths in output instead of the default relative paths')
    
    # Load the analyzer with dummy args to get plugin list
    # This is necessary to allow plugins to add their own arguments
    dummy_args = argparse.Namespace()
    analyzer = CodebaseAnalyzer(dummy_args)
    
    # Let each plugin add its own arguments
    # This ensures plugins can customize their behavior through command line options
    for plugin in analyzer.plugins.values():
        plugin.add_arguments(parser)
    
    # Parse the actual command line arguments
    args = parser.parse_args()
    
    # Create and run the analyzer with the real arguments
    analyzer = CodebaseAnalyzer(args)
    analyzer.generate_outputs()

if __name__ == "__main__":
    main()

    # python single-file/singlefile.py . --pattern_ignore_directories "^venv$" "^lib$" "^include$" "^bin$" "^lib64$" --output-dir ./output --formats default