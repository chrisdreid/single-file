import re
from pathlib import Path
from typing import Union

DEFAULT_IGNORE_PATTERNS = {
            'directories': [
                r'^\.git$',
                r'^\.svn$',
                r'^\.hg$',
                r'^__pycache__$',
                r'^\.pytest_cache$',
                r'^node_modules$',
                r'^\.[^/]*$'
            ],
            'files': [
                r'.*\.pyc$',
                r'.*\.pyo$',
                r'.*\.pyd$',
                r'.*~$',
                r'\.DS_Store$',
                r'Thumbs\.db$'
            ]
        }

CODEBASE_ANALYZER = 'CodebaseAnalyzer'

def read_file_with_encoding_gymnastics(file_path):
    """
    Attempts to read a file by trying different encodings in a prioritized order.
    This function provides a robust way to read files with unknown encodings by
    attempting multiple common encodings in sequence.
    
    Args:
        file_path: The path to the file we want to read
        
    Returns:
        str: The contents of the file
        
    Raises:
        ValueError: If the file cannot be read with any of the attempted encodings
    """
    # We try encodings in order of likelihood, optimizing for common cases
    encoding_attempts = [
        'utf-8',        # Most common encoding for modern files
        'utf-8-sig',    # UTF-8 with BOM (common in Windows)
        'ascii',        # Simple ASCII encoding
        'iso-8859-1',   # Latin-1 encoding (common in legacy systems)
        'cp1252',       # Windows-1252 encoding
        'utf-16',       # UTF-16 encoding
        'utf-16-le',    # UTF-16 Little Endian
        'utf-16-be'     # UTF-16 Big Endian
    ]
    
    failed_attempts = []
    
    # Try each encoding until one works
    for encoding in encoding_attempts:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError as e:
            failed_attempts.append(f"Tried {encoding} but it said: {str(e)}")
            continue
        except Exception as e:
            # If we get a different kind of error, it's probably not encoding-related
            raise
    
    # Last resort: Replace invalid characters with question marks
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            print(f"Warning: Had to replace some invalid characters in {file_path}")
            return content
    except Exception as e:
        failed_attempts.append(f"Even our last resort failed: {str(e)}")
    
    # If we get here, nothing worked
    raise ValueError(f"Failed to read {file_path} with all encodings:\n" + 
                    "\n".join(failed_attempts))

def format_path_for_output(path: Union[str, Path], base_path: Union[str, Path], 
                          force_absolute: bool = False) -> str:  # Changed return type to str
    """
    Formats a path for output, ensuring relative paths start with './'.
    
    This function handles several cases:
    1. Absolute paths when forced
    2. Relative paths that should start with './'
    3. Paths that go outside the base directory
    """
    # Convert and resolve both paths
    path = Path(path).resolve()
    base_path = Path(base_path).resolve()
    
    if force_absolute:
        return str(path)
        
    try:
        # Create relative path
        relative_path = path.relative_to(base_path)
        relative_str = str(relative_path)
        
        # If path would go up directories, return absolute
        if relative_str.startswith('..'):
            return str(path)
            
        # Always add './' for relative paths, unless path is exactly '.'
        if relative_str == '.':
            return relative_str
        return f'./{relative_str}'
            
    except ValueError:
        # If we can't make it relative, return absolute
        return str(path)
    
def should_include_path(analyzer, path: Path, is_dir: bool = False) -> bool:
    """
    Determine if a path should be included based on our filtering criteria.
    This method checks directories against directory patterns and files against
    file patterns, ensuring consistent filtering throughout the output.
    
    Args:
        path: The path to check for inclusion
        is_dir: Whether this path is a directory
        
    Returns:
        True if the path should be included, False if it should be ignored
    """
    if is_dir and analyzer.args.pattern_ignore_directories:
        for pattern in analyzer.args.pattern_ignore_directories:
            try:
                if re.search(pattern, str(path.name)):
                    return False
            except re.error:
                print(f"Warning: Invalid regex pattern '{pattern}'")
    return True