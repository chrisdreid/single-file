# plugins/json_output.py
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from single_file.core import OutputPlugin, argparse
# from single_file.utils import read_file_with_encoding_gymnastics, format_path_for_output

class JSONOutputPlugin(OutputPlugin):
    """
    Plugin that generates JSON output with configurable content and structure.
    Supports pretty printing, selective content inclusion, and detailed metadata.
    """
    format_name = 'json'
    
    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """
        Add JSON-specific command line arguments for customizing output.
        
        Args:
            parser: The argument parser to add arguments to
        """
        group = parser.add_argument_group('JSON output options')
        group.add_argument('--json-pretty', action='store_true',
                          help='Pretty-print JSON output')
        group.add_argument('--json-content', action='store_true',
                          help='Include file contents in JSON output')
        group.add_argument('--json-metadata', action='store_true',
                          help='Include detailed file metadata')
    
    def generate_output(self, output_path: Path) -> None:
        """
        Generate JSON output with the analyzed codebase data.
        
        Args:
            output_path: Path where the JSON file should be written
        """
        data = self._build_json_data()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # Use pretty printing if requested
            indent = 2 if self.analyzer.args.json_pretty else None
            json.dump(data, f, indent=indent, default=str)
    
    def _build_json_data(self) -> Dict[str, Any]:
        """
        Build the complete JSON data structure including metadata and file information.
        
        Returns:
            Dictionary containing all the codebase analysis data
        """
        return {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'analyzed_paths': [str(p) for p in self.analyzer.args.paths],
                'total_files': self.analyzer.stats['total_files'],
                'total_size': self.analyzer.stats['total_size'],
                'analysis_parameters': {
                    'depth': self.analyzer.args.depth,
                    'skip_errors': self.analyzer.args.skip_errors
                }
            },
            'statistics': {
                'file_types': self.analyzer.stats['extensions'],
                'largest_files': [
                    {'path': str(p), 'size': s}
                    for p, s in self.analyzer.stats['largest_files']
                ],
                'recent_changes': [
                    {'path': str(p), 'modified': m.isoformat()}
                    for p, m in self.analyzer.stats['recently_modified']
                ]
            },
            'files': self._build_files_data()
        }
    
    def _build_files_data(self) -> List[Dict[str, Any]]:
        """
        Build the files portion of the JSON data, respecting content inclusion settings.
        
        Returns:
            List of dictionaries containing file information
        """
        files_data = []
        
        for file_info in self.analyzer.file_info_cache.values():
            # Basic file information always included
            file_data = {
                'path': str(file_info['path']),
                'relative_path': str(file_info['relative_path']),
                'size': file_info['size'],
                'modified': file_info['modified'].isoformat(),
                'extension': file_info['extension'],
                'is_binary': file_info['is_binary']
            }
            
            # Add content if requested and available
            if self.analyzer.args.json_content and not file_info['is_binary']:
                file_data['content'] = file_info['content']
            
            # Add detailed metadata if requested
            if self.analyzer.args.json_metadata:
                file_data.update({
                    'hash': file_info['hash'],
                    'stats': {
                        'lines': len(file_info['content'].splitlines())
                        if not file_info['is_binary'] and file_info['content']
                        else None,
                        'size_human': self._format_size(file_info['size'])
                    }
                })
            
            files_data.append(file_data)
        
        return files_data
    
    @staticmethod
    def _format_size(size: int) -> str:
        """
        Format a file size in bytes to a human-readable string.
        
        Args:
            size: Size in bytes
            
        Returns:
            Human-readable size string (e.g., "1.5 MB")
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"