# single_file/plugins/json_output.py
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from single_file.core import OutputPlugin
from single_file.utils import format_path_for_output, should_include_path

class JSONOutputPlugin(OutputPlugin):
    """
    Generates a comprehensive JSON representation of the codebase, including
    directory structure, file contents, and metadata. This format maintains
    all the information from the default format while providing structured
    data that can be easily processed programmatically.
    """
    format_name = 'json'
    
    @classmethod
    def add_arguments(cls, parser) -> None:
        """
        Add JSON-specific command line arguments. Note that content inclusion
        and tree structure are now defaults, with options to disable them if needed.
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

    def generate_output(self, output_path: Path) -> None:
        include_metadata = getattr(self.analyzer.args, 'json_metadata', False)
        
        data = {
            'structure': self._build_directory_tree(),
            'files': self._build_files_data(),
            'statistics': self._build_statistics()
        }
        
        # Only include metadata if explicitly requested
        if include_metadata:
            data['metadata'] = {
                'generated_at': datetime.now().isoformat(),
                'tool_version': '1.0.0',
                'command_args': vars(self.analyzer.args),
                'analyzed_paths': [str(p) for p in self.analyzer.args.paths]
            }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(
                data,
                f,
                indent=None if getattr(self.analyzer.args, 'json_compact', False) else 2,
                default=str
            )

    def _build_directory_tree(self) -> List[Dict[str, Any]]:
        """
        Creates a hierarchical representation of the directory structure that
        mirrors the layout shown in the default format.
        """
        def build_tree(path: Path) -> Dict[str, Any]:
            result = {
                'type': 'directory',
                'name': path.name,
                'path': format_path_for_output(
                    path,
                    self.analyzer.args.paths[0],
                    getattr(self.analyzer.args, 'absolute_paths', False)
                ),
                'children': []
            }
            
            try:
                items = sorted(path.iterdir())
                for item in items:
                    if not should_include_path(self.analyzer, item):
                        continue
                        
                    if item.is_dir():
                        result['children'].append(build_tree(item))
                    else:
                        file_info = self.analyzer.analyze_file(item)
                        if file_info:
                            child = {
                                'type': 'file',
                                'name': item.name,
                                'path': format_path_for_output(
                                    item,
                                    self.analyzer.args.paths[0],
                                    getattr(self.analyzer.args, 'absolute_paths', False)
                                ),
                                'size': file_info['size'],
                                'size_human': self._format_size(file_info['size']),
                                'modified': file_info['modified'].isoformat(),
                                'is_binary': file_info['is_binary']
                            }
                            result['children'].append(child)
            except PermissionError:
                result['error'] = 'Permission denied'
            
            return result

        return [build_tree(Path(p)) for p in self.analyzer.args.paths]

    def _build_files_data(self) -> List[Dict[str, Any]]:
        """
        Creates detailed entries for each file, including contents by default.
        This ensures no information is lost compared to the default format.
        """
        files_data = []
        include_content = not getattr(self.analyzer.args, 'json_no_content', False)
        
        for file_info in self.analyzer.file_info_cache.values():
            file_data = {
                'path': format_path_for_output(
                    file_info['path'],
                    self.analyzer.args.paths[0],
                    getattr(self.analyzer.args, 'absolute_paths', False)
                ),
                'name': file_info['path'].name,
                'size': file_info['size'],
                'size_human': self._format_size(file_info['size']),
                'modified': file_info['modified'].isoformat(),
                'extension': file_info['extension'],
                'is_binary': file_info['is_binary'],
                'hash': file_info['hash']
            }

            # Include content for non-binary files unless explicitly disabled
            if include_content and not file_info['is_binary']:
                file_data['content'] = file_info['content']
                file_data['line_count'] = len(file_info['content'].splitlines())

            # Always include basic stats for binary files
            if file_info['is_binary']:
                file_data['content_type'] = 'binary'

            # Include file metadata
            try:
                stat = file_info['path'].stat()
                file_data['metadata'] = {
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'accessed': datetime.fromtimestamp(stat.st_atime).isoformat(),
                    'permissions': oct(stat.st_mode),
                    'owner': stat.st_uid,
                    'group': stat.st_gid
                }
            except Exception:
                pass

            files_data.append(file_data)
        
        return sorted(files_data, key=lambda x: x['path'])

    def _build_statistics(self) -> Dict[str, Any]:
        """
        Provides comprehensive statistics about the codebase, similar to
        what would be available in the default format.
        """
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
                        p, self.analyzer.args.paths[0],
                        getattr(self.analyzer.args, 'absolute_paths', False)
                    ),
                    'size': s,
                    'size_human': self._format_size(s)
                }
                for p, s in stats['largest_files']
            ],
            'recent_changes': [
                {
                    'path': format_path_for_output(
                        p, self.analyzer.args.paths[0],
                        getattr(self.analyzer.args, 'absolute_paths', False)
                    ),
                    'modified': m.isoformat()
                }
                for p, m in stats['recently_modified']
            ]
        }

    @staticmethod
    def _format_size(size: int) -> str:
        """
        Converts file sizes to human-readable format.
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"