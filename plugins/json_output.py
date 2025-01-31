import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import argparse
from single_file.core import OutputPlugin, BaseArguments
from single_file.utils import format_path_for_output, should_include_path

class JSONArguments(BaseArguments):
    """
    Extended arguments specific to JSON output plugin.
    Inherits all core arguments from BaseArguments.
    """
    def __init__(self):
        super().__init__()
        self.json_no_content: bool = False
        self.json_no_tree: bool = False
        self.json_compact: bool = False
        self.json_metadata: bool = False

    @classmethod
    def from_namespace(cls, namespace: argparse.Namespace) -> 'JSONArguments':
        """Create JSONArguments from parsed namespace."""
        instance = super().from_namespace(namespace)
        for key in ['json_no_content', 'json_no_tree', 'json_compact', 'json_metadata']:
            if hasattr(namespace, key):
                setattr(instance, key, getattr(namespace, key))
        return instance

class JSONOutputPlugin(OutputPlugin):
    """
    Generates a comprehensive JSON representation of the codebase.
    Supports additional JSON-specific formatting options.
    """
    format_name = 'json'
    
    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """
        Add JSON-specific command line arguments.
        These extend the core arguments from BaseArguments.
        """
        group = parser.add_argument_group('JSON output options')
        group.add_argument('--json-no-content', action='store_true',
                          help='Exclude file contents from JSON output')
        group.add_argument('--json-no-tree', action='store_true',
                          help='Exclude directory tree from output')
        group.add_argument('--json-compact', action='store_true',
                          help='Output minified JSON instead of pretty-printed')
        group.add_argument('--json-metadata', action='store_true',
                          help='Include metadata in JSON output (default: off)')

    def __init__(self, analyzer):
        """
        Initialize plugin with analyzer and convert args to JSONArguments.
        """
        super().__init__(analyzer)
        # Convert base args to JSON-specific args
        if not isinstance(self.args, JSONArguments):
            self.args = JSONArguments.from_namespace(analyzer.args)

    def generate_output(self, output_path: Path) -> None:
        """
        Generate JSON output according to configured options.
        
        Args:
            output_path: Where to write the JSON file
            
        Note:
            This method can process and write large amounts of data.
            Ensure sufficient disk space and memory.
        """
        data: Dict[str, Any] = {}
        
        # Only include tree if not disabled
        if not self.args.json_no_tree:
            data['structure'] = self._build_directory_tree()
        
        # Always include files data
        data['files'] = self._build_files_data()
        data['statistics'] = self._build_statistics()
        
        # Include metadata if requested
        if self.args.json_metadata:
            data['metadata'] = {
                'generated_at': datetime.now().isoformat(),
                'tool_version': '1.0.0',
                'command_args': vars(self.args),
                'analyzed_paths': [str(p) for p in self.args.paths]
            }
        
        # Write output with appropriate formatting
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(
                data,
                f,
                indent=None if self.args.json_compact else 2,
                default=str  # Handle non-serializable types
            )

    def _build_directory_tree(self) -> List[Dict[str, Any]]:
        """
        Creates a hierarchical representation of the directory structure.
        Honors depth limits and filtering options.
        """
        def build_tree(path: Path, current_depth: int = 0) -> Dict[str, Any]:
            result = {
                'type': 'directory',
                'name': path.name,
                'path': format_path_for_output(
                    path,
                    self.args.paths[0],
                    self.args.absolute_paths
                ),
                'children': []
            }
            
            # Honor depth limit if set
            if self.args.depth > 0 and current_depth >= self.args.depth:
                return result
            
            try:
                items = sorted(path.iterdir())
                for item in items:
                    if not self.analyzer.file_collector.should_include_path(item, is_dir=item.is_dir()):
                        continue
                        
                    if item.is_dir():
                        result['children'].append(
                            build_tree(item, current_depth + 1)
                        )
                    else:
                        file_info = self.analyzer.analyze_file(item)
                        if file_info:
                            child = {
                                'type': 'file',
                                'name': item.name,
                                'path': format_path_for_output(
                                    item,
                                    self.args.paths[0],
                                    self.args.absolute_paths
                                ),
                                'size': file_info['size'],
                                'size_human': self._format_size(file_info['size']),
                                'modified': file_info['modified'].isoformat()
                            }
                            result['children'].append(child)
            except PermissionError:
                result['error'] = 'Permission denied'
            
            return result

        return [build_tree(Path(p)) for p in self.args.paths]

    def _build_files_data(self) -> List[Dict[str, Any]]:
        """
        Creates detailed entries for each file.
        Respects content inclusion setting.
        """
        files_data = []
        
        for file_info in self.analyzer.file_info_cache.values():
            file_data = {
                'path': format_path_for_output(
                    file_info['path'],
                    self.args.paths[0],
                    self.args.absolute_paths
                ),
                'name': file_info['path'].name,
                'size': file_info['size'],
                'size_human': self._format_size(file_info['size']),
                'modified': file_info['modified'].isoformat(),
                'extension': file_info['extension'],
                'is_binary': file_info['is_binary'],
                'hash': file_info['hash']
            }

            # Include content only if enabled and non-binary
            if not self.args.json_no_content and not file_info['is_binary']:
                file_data['content'] = file_info['content']
                file_data['line_count'] = len(file_info['content'].splitlines())
            
            files_data.append(file_data)
        
        return sorted(files_data, key=lambda x: x['path'])

    def _build_statistics(self) -> Dict[str, Any]:
        """Generate comprehensive codebase statistics."""
        stats = self.analyzer.stats
        return {
            'summary': {
                'total_files': stats['total_files'],
                'total_size': stats['total_size'],
                'total_size_human': self._format_size(stats['total_size'])
            },
            'extensions': {
                ext: {'count': count, 'extension': ext or 'no extension'}
                for ext, count in stats['extensions'].items()
            },
            'largest_files': [
                {
                    'path': format_path_for_output(
                        p, self.args.paths[0],
                        self.args.absolute_paths
                    ),
                    'size': s,
                    'size_human': self._format_size(s)
                }
                for p, s in stats['largest_files']
            ],
            'recent_changes': [
                {
                    'path': format_path_for_output(
                        p, self.args.paths[0],
                        self.args.absolute_paths
                    ),
                    'modified': m.isoformat()
                }
                for p, m in stats['recently_modified']
            ]
        }