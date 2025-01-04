# SingleFile: Code Flattening Tool

SingleFile is a Python tool that makes it easy to share your code with AI language models like ChatGPT and Claude. It takes your project's files and directory structure and transforms them into a single, readable document. This makes it simple for AI models to understand your entire codebase and provide more accurate assistance.

This tool is inspired by [flatten-codebase](https://github.com/VictorHenrique317/flatten-codebase) but adds enhanced features like flexible output formats and improved path handling. It's designed to be lightweight and easy to use, whether you're working directly with AI assistants or building IDE extensions.

## Why Use SingleFile?

When working with AI language models, context is everything. Trying to explain multiple files and complex directory structures piece by piece can be frustrating and lead to confusion. SingleFile solves this by creating one document that preserves both your code and its organization.

Think of it like creating a book from your project - the table of contents shows how everything is organized, and each chapter contains the contents of a file. This makes it easy for AI models to "read" your project and understand how everything fits together.

## Installation

SingleFile is built using only Python's standard library, making installation as simple as cloning the repository. There are no additional dependencies to manage or complex setup processes to follow.

```bash
git clone https://github.com/chrisdreid/single_file.git
cd single_file
```

That's it - you're ready to start using SingleFile.

## Command-Line Options

SingleFile provides a variety of command-line options to control how your code is processed and output:

```bash
python single_file/singlefile.py [options] path [path ...]
```

Core Options:
- `path`: One or more paths to analyze (required)
- `--output-dir`: Directory where output files will be created (default: ./output)
- `--formats`: Comma-separated list of output formats to generate (default: default)
- `--depth`: Maximum directory depth to traverse (0 = unlimited)
- `--skip-errors`: Continue processing even if some files can't be read
- `--absolute-paths`: Use absolute paths in output instead of relative paths

Directory and File Filtering:
- `--pattern_ignore_directories`: Regex patterns for directories to ignore
- `--pattern_only_directories`: Regex patterns for directories to include
- `--pattern_ignore_files`: Regex patterns for files to ignore
- `--pattern_only_files`: Regex patterns for files to include
- `--ext_only`: Only include files with these extensions
- `--ext_ignore`: Ignore files with these extensions

## Understanding Regex Patterns

SingleFile uses regular expressions (regex) for powerful and flexible file/directory filtering. Here are some common patterns:

```bash
# Exact matches (anchored)
"^venv$"           # Matches exactly "venv"
"^node_modules$"   # Matches exactly "node_modules"

# Partial matches
"\.git"            # Matches any path containing ".git"
"_test$"           # Matches paths ending in "_test"
"^test_"           # Matches paths starting with "test_"

# Common patterns
".*cache"          # Matches anything ending in "cache"
"\.pyc$"           # Matches Python compiled files
"^__pycache__$"    # Matches Python cache directories

# Example usage
python single_file/singlefile.py ./ \
  --pattern_ignore_directories "\.git" "^venv$" "^node_modules$" "^__pycache__$" \
  --pattern_ignore_files "\.pyc$" "\.pyo$" "\.pyd$" \
  --output-dir ./output \
  --formats default
```

## Output Example

The default output format looks like this:

```
### DIRECTORY ./my-project FOLDER STRUCTURE ###
src/
    main.py
    utils/
        helpers.py
### DIRECTORY ./my-project FOLDER STRUCTURE ###

### ./src/main.py BEGIN ###
[file contents here]
### ./src/main.py END ###
```

## Output Formats

SingleFile supports different ways to view your code:

1. Default Format: Optimized for AI language models, showing both structure and content
2. Markdown: Creates readable documentation with syntax highlighting
3. JSON: Provides structured data perfect for programmatic processing

You can generate multiple formats at once:

```bash
python single_file/singlefile.py ./my-project \
  --pattern_ignore_directories "\.git" "^venv$" \
  --formats markdown,json \
  --output-dir ./documentation
```

## Extending SingleFile

SingleFile uses a plugin system that makes it easy to add new features. Each plugin is a Python class that controls how your code is presented. Here's a simple example:

```python
from single_file.core import OutputPlugin
from pathlib import Path

class CustomOutputPlugin(OutputPlugin):
    format_name = 'custom'
    
    def generate_output(self, output_path: Path) -> None:
        with open(output_path, 'w', encoding='utf-8') as f:
            # Your custom output generation code here
            pass
```

To create a new plugin:
1. Create a new .py file in the plugins directory
2. Define a class that inherits from OutputPlugin
3. Set a unique format_name
4. Implement the generate_output method

SingleFile will automatically discover and use your plugin.

## Future Development

SingleFile is designed to grow with your needs. The plugin architecture means you can:
- Create new output formats
- Add analysis tools
- Integrate with different development tools
- Customize how your code is presented to AI models

## Contributing

We welcome contributions that help make SingleFile more useful. Whether you're fixing bugs, adding features, or improving documentation, your help makes the tool better for everyone.

## Credits

This tool builds upon the work of Victor Henrique's flatten-codebase project, extending its capabilities to better serve modern AI-assisted development workflows.

## License

MIT License

---

SingleFile: Making code sharing with AI as easy as possible.
