# single_file_dev01/single_file/utils.py

import re
from pathlib import Path
from typing import Union

DEFAULT_IGNORE_PATTERNS = {
    "directories": [
        r"^\.git$",
        r"^\.svn$",
        r"^\.hg$",
        r"^__pycache__$",
        r"^\.pytest_cache$",
        r"^node_modules$",
        r"^\.[^/]*$",
    ],
    "files": [
        r".*\.pyc$",
        r".*\.pyo$",
        r".*\.pyd$",
        r".*~$",
        r"\.DS_Store$",
        r"Thumbs\.db$",
    ],
}

CODEBASE_ANALYZER = "CodebaseAnalyzer"


def read_file_with_encoding_gymnastics(file_path):
    """
    Attempts to read a file by trying different encodings in a prioritized order.
    """
    encoding_attempts = [
        "utf-8",
        "utf-8-sig",
        "ascii",
        "iso-8859-1",
        "cp1252",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
    ]

    failed_attempts = []

    for encoding in encoding_attempts:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError as e:
            failed_attempts.append(f"Tried {encoding} but it said: {str(e)}")
            continue
        except Exception as e:
            raise

    # Last resort: Replace invalid characters
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            print(f"Warning: Had to replace some invalid characters in {file_path}")
            return content
    except Exception as e:
        failed_attempts.append(f"Even our last resort failed: {str(e)}")

    raise ValueError(
        f"Failed to read {file_path} with all encodings:\n" + "\n".join(failed_attempts)
    )


def format_path_for_output(
    path: Union[str, Path], base_path: Union[str, Path], force_absolute: bool = False
) -> str:
    """
    Formats a path for output, ensuring relative paths start with './'.
    """
    path = Path(path).resolve()
    base_path = Path(base_path).resolve()

    if force_absolute:
        return str(path)

    try:
        relative_path = path.relative_to(base_path)
        relative_str = str(relative_path)
        if relative_str.startswith(".."):
            return str(path)
        if relative_str == ".":
            return relative_str
        return f"./{relative_str}"
    except ValueError:
        return str(path)
