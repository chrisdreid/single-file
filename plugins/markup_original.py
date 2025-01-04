# plugins/markdown_output.py
from datetime import datetime
from pathlib import Path
from typing import TextIO, List, Dict
from single_file.core import OutputPlugin, argparse
# from single_file.utils import read_file_with_encoding_gymnastics, format_path_for_output

class MarkdownOutputPlugin(OutputPlugin):
    """
    Plugin that generates rich Markdown documentation of the codebase,
    including navigation, statistics, and formatted code blocks.
    """
    format_name = 'markdown'
    
    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """
        Add Markdown-specific command line arguments.
        
        Args:
            parser: The argument parser to add arguments to
        """
        group = parser.add_argument_group('Markdown output options')
        group.add_argument('--md-toc', action='store_true',
                          help='Include table of contents')
        group.add_argument('--md-stats', action='store_true',
                          help='Include codebase statistics')
        group.add_argument('--md-syntax', action='store_true',
                          help='Add syntax highlighting hints')
    
    def generate_output(self, output_path: Path) -> None:
        """
        Generate comprehensive Markdown documentation.
        
        Args:
            output_path: Path where the Markdown file should be written
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write document header
            self._write_header(f)
            
            # Write table of contents if requested
            if self.analyzer.args.md_toc:
                self._write_toc(f)
            
            # Write statistics if requested
            if self.analyzer.args.md_stats:
                self._write_statistics(f)
            
            # Write file contents
            self._write_file_contents(f)
    
    def _write_header(self, f: TextIO) -> None:
        """Write the document header with title and metadata."""
        f.write("# Codebase Documentation\n\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Analyzed Paths\n\n")
        for path in self.analyzer.args.paths:
            f.write(f"- `{path}`\n")
        f.write("\n")
    
    def _write_toc(self, f: TextIO) -> None:
        """Write a table of contents with links to sections."""
        f.write("## Table of Contents\n\n")
        
        # Add statistics section if included
        if self.analyzer.args.md_stats:
            f.write("1. [Statistics](#statistics)\n")
        
        # Add file listing
        f.write("2. [Files](#files)\n")
        
        # Add links to each file
        for file_info in self.analyzer.file_info_cache.values():
            relative_path = str(file_info['relative_path'])
            anchor = self._make_anchor(relative_path)
            indent = '   ' * (relative_path.count('/') + 1)
            f.write(f"{indent}- [{relative_path}](#{anchor})\n")
        
        f.write("\n")
    
    def _write_statistics(self, f: TextIO) -> None:
        """Write detailed codebase statistics."""
        f.write("## Statistics\n\n")
        
        # Overall statistics
        f.write("### Overview\n\n")
        f.write(f"- Total Files: {self.analyzer.stats['total_files']}\n")
        f.write(f"- Total Size: {self._format_size(self.analyzer.stats['total_size'])}\n\n")
        
        # File types
        f.write("### File Types\n\n")
        f.write("| Extension | Count |\n")
        f.write("|-----------|-------|\n")
        for ext, count in sorted(self.analyzer.stats['extensions'].items()):
            f.write(f"| {ext or '(no extension)'} | {count} |\n")
        f.write("\n")
        
        # Largest files
        f.write("### Largest Files\n\n")
        f.write("| File | Size |\n")
        f.write("|------|------|\n")
        for path, size in self.analyzer.stats['largest_files']:
            f.write(f"| `{path}` | {self._format_size(size)} |\n")
        f.write("\n")
        
        # Recent changes
        f.write("### Recent Changes\n\n")
        f.write("| File | Modified |\n")
        f.write("|------|----------|\n")
        for path, modified in self.analyzer.stats['recently_modified']:
            f.write(f"| `{path}` | {modified.strftime('%Y-%m-%d %H:%M:%S')} |\n")
        f.write("\n")
    
    def _write_file_contents(self, f: TextIO) -> None:
        """Write the contents of each file with proper formatting."""
        f.write("## Files\n\n")
        
        for file_info in sorted(
            self.analyzer.file_info_cache.values(),
            key=lambda x: str(x['relative_path'])
        ):
            relative_path = str(file_info['relative_path'])
            anchor = self._make_anchor(relative_path)
            
            # File header
            f.write(f"### <a id='{anchor}'></a>{relative_path}\n\n")
            
            # File metadata
            f.write("**File Information:**\n\n")
            f.write(f"- Size: {self._format_size(file_info['size'])}\n")
            f.write(f"- Modified: {file_info['modified'].strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- Type: {file_info['extension'] or '(no extension)'}\n\n")
            
            # File contents
            if file_info['is_binary']:
                f.write("*Binary file contents omitted*\n\n")
            else:
                language = self._get_language_hint(file_info['extension'])
                fence = '```' + (language if self.analyzer.args.md_syntax else '')
                f.write(f"{fence}\n{file_info['content']}\n```\n\n")
            
            f.write("---\n\n")
    
    @staticmethod
    def _make_anchor(path: str) -> str:
        """
        Create a valid HTML anchor from a file path.
        
        Args:
            path: File path to convert
            
        Returns:
            Anchor-safe string
        """
        return path.replace('/', '-').replace('.', '-').lower()
    
    @staticmethod
    def _format_size(size: int) -> str:
        """
        Format a file size in bytes to a human-readable string.
        
        Args:
            size: Size in bytes
            
        Returns:
            Human-readable size string
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    @staticmethod
    def _get_language_hint(extension: str) -> str:
        """
        Get the markdown code fence language hint for a file extension.
        
        Args:
            extension: File extension
            
        Returns:
            Language identifier for syntax highlighting
        """
        language_map = {
            'py': 'python',
            'js': 'javascript',
            'jsx': 'jsx',
            'ts': 'typescript',
            'tsx': 'tsx',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'c',
            'cs': 'csharp',
            'go': 'go',
            'rs': 'rust',
            'rb': 'ruby',
            'php': 'php',
            'html': 'html',
            'css': 'css',
            'scss': 'scss',
            'sql': 'sql',
            'md': 'markdown',
            'json': 'json',
            'yaml': 'yaml',
            'yml': 'yaml',
            'xml': 'xml',
            'sh': 'bash',
            'bash': 'bash',
        }
        return language_map.get(extension.lower(), '')