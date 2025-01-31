![Banner](./images/single-file_1280x317.png)

# SingleFile: A Powerful Code Flattening and Analysis Tool

SingleFile is a Python tool that **flattens** your project’s code into one or more coherent, self-contained representations. It’s designed primarily for sharing with AI language models (like ChatGPT) or for generating human-readable documentation. SingleFile also provides **analysis** features such as file statistics, directory scanning, and metadata plugins.

This repo was inspired by **flatten-codebase** @ https://github.com/VictorHenrique317/flatten-codebase.git <br>
Thanks Victor, [flatten-codebase](https://github.com/VictorHenrique317/flatten-codebase.git) was used extensively in the begginging of the project, until it could do it itself.

> <mark>**Self-Bootstrapping**</mark>  
>  
> This repository leveraged its **own code** to build itself—Thanks AI, this **could** have been done without you... **but much slower**!


## Key Features

1. **Flatten Entire Codebases**  
   Gather all your files into a single textual output, preserving directory structure in a human-readable “table-of-contents” format.

2. **Multiple Output Formats**  
   Easily generate outputs in **default** (plain text), **Markdown**, or **JSON**, or **create your own** custom format via plugins.

3. **Powerful Filtering**  
   You can limit what files and directories are included with **regex-based** or **extension-based** filters (e.g., exclude `__pycache__`, only include `.py` files, etc.).

4. **Plugin Architecture**  
   SingleFile supports two types of plugins:
   - **Output Plugins**: Decide the final format (e.g., Markdown, JSON).
   - **Metadata Plugins**: Attach additional information to each file (e.g., MD5 checksums, base64 binary content).

5. **Config File Support**  
   Load your CLI settings from a JSON config file, merging with additional command-line arguments seamlessly.

6. **Error Handling & Logging**  
   Control scanning depth, continue or stop on errors, log warnings for skipped paths, and more.

---

## Repository Structure

```
single_file/
    README.md               <-- You are here
    setup.py                <-- Standard Python package setup
    output/                 <-- (Optional) Example output directory (if any)
    configs/
        python-project.json <-- Example config file
    single_file/
        __init__.py
        core.py             <-- Core classes (BaseArguments, FileCollector, OutputPlugin, etc.)
        singlefile.py       <-- Main "CodebaseAnalyzer" logic
        utils.py            <-- Utility functions
        plugins/
            __init__.py
            outputs/
                __init__.py
                default_output.py   <-- Default output format plugin
                json_output.py      <-- JSON output format plugin
                markdown_output.py  <-- Markdown output format plugin
            metadata/
                __init__.py
                plugin_base.py      <-- Base class for metadata plugins
                binary_content.py   <-- Base64-encode binary files plugin
                md5_hash.py         <-- MD5 hashing plugin
    tests/
        test_basic.py
        test_plugins.py
```

- **setup.py**: Enables installation via `pip install .` within this repo.  
- **configs/python-project.json**: An example JSON config demonstrating how you can preload CLI arguments.

---

## Installation

### Option 1: Install Locally

1. Clone the repo:
   ```bash
   git clone https://github.com/your-username/single_file.git
   cd single_file
   ```

2. Install with pip (in editable/developer mode):
   ```bash
   pip install -e .
   ```
   This will register the console script (once renamed) so you can run it with a command `single_file` (or your chosen entry point) from anywhere on your system. It is especially important when you install our vscode extension (coming really soon).


### Option 2: Just Clone and Run
If you don’t want to install system-wide:
```bash
git clone https://github.com/chrisdreid/single_file.git
cd single_file
python -m single_file  --help
```
or
```bash
python single_file/__main__.py --help
```

---

## Usage

### Basic Command

```bash
python single_file/singlefile.py [options] path [path ...]
```

For example, if you want to flatten a `my_project` directory into a single text file:
```bash
python single_file/singlefile.py my_project \
  --output-file my_flattened_project.txt \
  --formats default
```
**Result**: Creates `my_flattened_project.txt` (using the **default** plugin) that shows directory structure and file contents.

### Command-Line Arguments

All core arguments are parsed in two phases so you can also load them from `--config` (JSON file) if desired. Here are some of the main options you might use:

**Paths & Output Options**
- `--paths [PATH ...]`: One or more directories/files to scan (default: `.`).
- `--output-file [OUTPUT]`: The base filename for outputs (default: `./output`).
- `--formats [FORMATS]`: Comma-separated output formats. Examples: `default`, `json`, `markdown` or `json,markdown`.

**Filters & Depth**
- `--depth [N]`: Limit recursion depth when scanning (0 = unlimited).
- `--extensions [EXT ...]`: Only include files with these extensions (e.g., `--extensions py js`).
- `--exclude-extensions [EXT ...]`: Exclude files with these extensions.
- `--exclude-dirs [REGEX ...]`: Exclude directories matching these regex patterns (default includes ignoring `.git`, `__pycache__`, etc.).
- `--exclude-files [REGEX ...]`: Exclude files matching these regex patterns.
- `--include-dirs [REGEX ...]`: Only include directories matching these patterns (otherwise exclude them).
- `--include-files [REGEX ...]`: Only include files matching these patterns (otherwise exclude them).

**Handling Errors & Paths**
- `--ignore-errors`: Continue even if some paths/files cause errors.
- `--replace-invalid-chars`: Replace unrecognized byte sequences in text files rather than failing.
- `--absolute-paths`: Use absolute file paths in output instead of relative paths.

**Metadata Controls**
- `--metadata-add [FIELDS ...]`: Add one or more metadata fields (e.g. `md5`, `binary_content`) to each file.
- `--metadata-remove [FIELDS ...]`: Remove default metadata fields (like `size`, `modified`, etc.).
- `--force-binary-content`: Actually read binary files and store base64-encoded data instead of skipping them.

**Plugins**
- `--disable-plugin [NAME ...]`: Disable specific plugins by format name.  
  Example: `--disable-plugin json` will skip the JSON output plugin if you had it configured.

**Config File**
- `--config [FILE]`: Load arguments from a JSON config. Values in the file get merged into the command-line arguments.

---

## Example Commands

### 1. Generate Default (Plain Text) Flattened Output
```bash
python single_file/singlefile.py ./my_project \
  --formats default \
  --output-file my_project_flattened.txt
```
You’ll get:
```
### DIRECTORY ./my_project FOLDER STRUCTURE ###
my_project/
    main.py
    utils/
        helpers.py
### DIRECTORY ./my_project FOLDER STRUCTURE ###

### ./my_project/main.py BEGIN ###
[contents of main.py]
### ./my_project/main.py END ###
```

### 2. Generate JSON and Markdown Simultaneously
##### Note: JSON is the best way to pass flattened codebases to AI models for most coding tasks.

```bash
python single_file/singlefile.py ./my_project \
  --formats json,markdown \
  --output-file ./output/my_project
```
This will create **`my_project.json`** and **`my_project.md`** inside the `./output` folder. Each plugin controls the file extension automatically.

### 3. Use a Config File
```bash
python single_file/singlefile.py \
  --config configs/python-project.json
```
Then add or override arguments:
```bash
python single_file/singlefile.py \
  --config configs/python-project.json \
  --absolute-paths \
  --formats markdown
```

Sample `python-project.json`:
```json
{
  "paths": ["./"],
  "output_file": "single-file-output.json",
  "exclude_dirs": [".git", "__pycache__"],
  "extensions": ["py", "json"]
}
```

---

## Output Plugins

SingleFile includes several built-in output plugins:

1. **Default**  
   - Format Name: `default`  
   - Extension: `.txt`  
   - Produces a flattened text file with directory structure and inline file contents.

2. **Markdown**  
   - Format Name: `markdown`  
   - Extension: `.md`  
   - Generates documentation-friendly Markdown, optionally with a table of contents (`--md-toc`), stats (`--md-stats`), and syntax highlighting (`--md-syntax`).

3. **JSON**  
   - Format Name: `json`  
   - Extension: `.json`  
   - Creates a JSON array of files, with optional file contents, metadata, and stats. Add `--json-no-content` for a structure-only view.

### Creating Your Own Output Plugin

Create a new file in `single_file/plugins/outputs`. For example:  
```python
# single_file/plugins/outputs/my_custom_output.py
from single_file.core import OutputPlugin
from pathlib import Path

class MyCustomOutputPlugin(OutputPlugin):
    format_name = "custom_format"
    supported_extensions = [".out"]

    def generate_output(self, output_path: Path) -> None:
        # Your logic to traverse self.analyzer.file_info_cache 
        # and produce the file in your desired format
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("Hello from MyCustomOutput!\n")
```
SingleFile will discover it automatically at runtime (unless disabled via `--disable-plugin`).

---

## Metadata Plugins

By default, SingleFile includes these metadata plugins:

- **MD5** (`md5_hash.py`)  
  Adds an `md5` field to each file (if `--metadata-add md5` is specified).
- **Binary Content** (`binary_content.py`)  
  Base64-encodes true binary files in their entirety (if `--metadata-add binary_content`).

### Creating Your Own Metadata Plugin

Simply create a new file under `single_file/plugins/metadata`. For example:
```python
from single_file.plugins.metadata.plugin_base import MetadataPlugin

class MyCustomMetadataPlugin(MetadataPlugin):
    metadata_name = "my_meta"

    def attach_metadata(self, file_info: dict) -> None:
        # Modify or attach extra fields to file_info
        file_info["my_meta"] = "some_value"
```
Then use `--metadata-add my_meta` in your CLI to include it.

---

## Running Tests

SingleFile uses standard Python `unittest`.

1. Install dev dependencies (if any).
2. From the project root, run:
   ```bash
   python -m unittest discover -s tests
   ```
3. See `tests/test_basic.py` and `tests/test_plugins.py` for examples.

---

## Contributing

We welcome contributions! Whether you have a feature idea, bug fix, or new documentation, feel free to open an issue or pull request. 

Possible areas for contribution:
- Additional **output plugins** (like HTML, CSV, or custom format).
- More **metadata plugins** (file checksums, code metrics, etc.).
- Integration with other tools or CI pipelines.
- Improved error handling or performance optimizations.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

**SingleFile**: Flatten, document, and analyze your codebase with ease.  
