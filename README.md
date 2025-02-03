
![Banner](./images/banner.png)

# SingleFile

SingleFile is a **codebase flattening and analysis** tool designed to unify multiple files and directories into comprehensive, metadata-rich outputs. Whether you need a simple text flatten for a single folder or an in-depth, multi-output metadata filled output for AI ingestion, SingleFile’s modular architecture can adapt to your exact requirements.

- **No External Dependencies**: Built exclusively on the Python Standard Library.  
- **Config-Driven**: Merge a JSON config file with CLI arguments for reproducible setups.  
- **Pluggable**: Add your own output/metadata plugins for specialized needs.  

<br>

---
## Acknowledgments

Special thanks to [@VictorHenrique317](https://github.com/VictorHenrique317) for his original work on [flatten-codebase](https://github.com/VictorHenrique317/flatten-codebase.git). SingleFile drew inspiration from flatten-codebase; And used flatten-codebase extensively to build this and many tools.

<br>

---
## Table of Contents

1. [Key Features](#key-features)  
2. [Installation](#installation)  
   - [Linux/macOS](#linuxmacos)  
   - [Windows](#windows)  
   - [Using Pyenv](#using-pyenv)  
3. [Environment Variables](#environment-variables)  
4. [Basic Usage](#basic-usage)  
   - [A Minimal One-Liner](#a-minimal-one-liner)  
   - [Simple Example with Defaults](#simple-example-with-defaults)  
5. [Intermediate Examples](#intermediate-examples)  
   - [Filtering and Custom Metadata](#filtering-and-custom-metadata)  
   - [Using a JSON Config](#using-a-json-config)  
6. [Advanced Examples](#advanced-examples)  
   - [Multiple Outputs](#multiple-outputs)  
   - [Querying Available Plugins and Configs](#querying-available-plugins-and-configs)  
   - [Running from Another Script](#running-from-another-script)  
7. [Plugin Architecture](#plugin-architecture)  
   - [Output Plugins](#output-plugins)  
   - [Metadata Plugins](#metadata-plugins)  
8. [VS Code Extension (Coming Soon)](#vs-code-extension-coming-soon)  
9. [Contributing & Development](#contributing--development)  
10. [Acknowledgments](#acknowledgments)  
11. [License](#license)  

<br>

---

## Key Features

- **Cross-Platform**: Works seamlessly on Windows, macOS, and Linux.  
- **Multiple Output Formats**: Text (`default`), Markdown, and JSON included. Write your own plugin for HTML, CSV, etc.  
- **Rich Metadata**: Default fields like file size, modified date, or extension. Add custom metadata—e.g., MD5 checksums or base64 binary content—through plugins.  
- **Powerful Filtering**: Use regex to include/exclude directories, files, or extensions.  
- **Two-Phase CLI**: 
  1. Global arguments (like `--config` and `--disable-plugin`)  
  2. Final pass merges JSON config + plugin-specific flags  
- **Zero Dependencies**: Only Python’s Standard Library—no extra pip installs or environment constraints.  

<br>

---

## Installation

### Linux/macOS

1. **Clone the repository**:
   ```bash
   git clone https://github.com/chrisdreid/single-file.git
   cd single-file
   ```
2. **Install** (editable mode recommended for development or plugin creation):
   ```bash
   pip install -e .
   ```
3. **Test** the installation:
   ```bash
   single-file --help
   ```
   or:
   ```bash
   python -m single-file --help
   ```

### Windows

1. **Clone or download**:
   ```powershell
   git clone https://github.com/chrisdreid/single-file.git
   cd single-file
   ```
2. **Install**:
   ```powershell
   pip install -e .
   ```
3. **Check** everything:
   ```powershell
   single-file --help
   ```
   If `single-file` isn’t recognized, verify your Python scripts directory is on the `PATH`, or use:
   ```powershell
   python -m single-file --help
   ```

### Using Pyenv

If you prefer isolating specific Python versions:

```bash
pyenv install 3.10.5
pyenv shell 3.10.5
pip install -e .
single-file --help
```

<br>

---

## Environment Variables

You can set the `SINGLEFILE_CONFIG_PATH` environment variable to point to one or more directories containing shared JSON config files:

- **macOS/Linux**:
  ```bash
  export SINGLEFILE_CONFIG_PATH="/home/myuser/singlefile_configs"
  ```
- **Windows (PowerShell)**:
  ```powershell
  $Env:SINGLEFILE_CONFIG_PATH = "C:\singlefile_configs"
  ```
- **Windows (cmd.exe)**:
  ```bat
  set SINGLEFILE_CONFIG_PATH=C:\singlefile_configs
  ```

To see which config files SingleFile finds, run:

```bash
single-file --query configs
```

<br>

---

## Basic Usage

### Simple Example with Defaults

```bash
single-file \
  --paths ./src \
  --output-file my_project_flat.txt
```

- Scans `./src` recursively with no depth limit.
- Creates a single text file: `my_project_flat.txt`.
- **No** advanced filters are applied. All files are included (unless caught by default ignore patterns like `.git`).

<br>

---

## Intermediate Examples

### Filtering and Custom Metadata

```bash
single-file \
  --output-file my-output.json \
  --paths ./my_app \
  --depth 2 \
  --exclude-dirs "^(\\.git|__pycache__)$" \
  --extensions py md \
  --metadata-add md5 \
  --metadata-remove size modified
```

**What’s Happening**:
- Scans `./my_app` up to **2 levels** deep.
- Excludes `.git` and `__pycache__` directories.
- Only processes `.py` and `.md` files.
- **Adds** MD5 checksums to each file’s metadata (`--metadata-add md5`).
- **Removes** default `size` and `modified` fields from output (`--metadata-remove size modified`).
- Outputs a single file named `my-output.json`.

### Using a JSON Config

You can store frequently used arguments in a JSON file, for instance `dev_rules.json`:

```json
{
  "paths": ["./my_app"],
  "exclude_dirs": [".git", "__pycache__"],
  "extensions": ["py", "md", "json"],
  "output_file": "my_app_flat",
  "formats": "markdown"
}
```

Then invoke:

```bash
single-file --config dev_rules.json --extensions py 
```

This updates the `dev_rules.json` config with any CLI overrides (`--extensions` in this example will only be 'py').  
**Result**: A single Markdown file `my_app_flat.md` containing code blocks plus codebase statistics.

<br>

---

## Advanced Examples

### Multiple Outputs

Generate both plain text **and** JSON outputs in one run:

```bash
single-file \
  --paths ./my_app \
  --formats default,json \
  --output-file consolidated \
  --ignore-errors
```

- Produces `consolidated.txt` and `consolidated.json`.
- If any permission or read errors occur, SingleFile will skip those entries instead of failing.

### Querying Available Plugins and Configs

```bash
single-file --query formats plugins metadata configs
```

**Returns** (in JSON):
- **formats**: All output plugins (with supported extensions, e.g., `.txt`, `.md`, `.json`).  
- **plugins**: Lists both output and metadata plugin names + descriptions.  
- **metadata**: Shows which fields are enabled by default, plus any plugin-specific fields (like `md5`, `binary_content`).
- **configs**: Identifies known JSON config files found in `SINGLEFILE_CONFIG_PATH` or the local `configs/` folder.

### Running from Another Script

You can run SingleFile programmatically (as a subprocess) and parse its JSON output:

```python
import subprocess, json

def run_singlefile_query(what="formats"):
    result = subprocess.run(
        ["single-file", "--query", what],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)

info = run_singlefile_query("formats")
print("Available output plugins:", info["formats"])
```

This approach is useful for dynamically building UI elements, gating logic on discovered plugins, or simply automating SingleFile in a larger pipeline.

<br>

---

## Plugin Architecture

SingleFile is highly extensible. Write your own output or metadata plugins to shape the final content to your exact needs.

### Output Plugins

- **Default** (`default`, `.txt`): Basic text flatten with file markers.  
- **Markdown** (`markdown`, `.md`): Adds code blocks, optional collapsible sections, and an auto-generated table of contents (`--md-toc`).  
- **JSON** (`json`, `.json`): Produces a structured JSON object capturing directory trees, file metadata, and file contents (optional flags like `--json-no-content` remove the content field).  

**To create a custom output plugin** (example: HTML):

```python
# single-file/plugins/outputs/html_output.py

from single_file.core import OutputPlugin
from pathlib import Path

class HTMLOutputPlugin(OutputPlugin):
    format_name = "html"
    supported_extensions = [".html"]

    def generate_output(self, output_path: Path) -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("<html><body>\n")
            f.write("<h1>Project Overview</h1>\n")
            for file_info in self.analyzer.file_info_cache.values():
                f.write(f"<h2>{file_info['filepath']}</h2>")
                content = file_info.get("content", "")
                f.write(f"<pre>{content}</pre>\n")
            f.write("</body></html>\n")
```

Then run it:

```bash
single-file --formats html
```

### Metadata Plugins

- **MD5** (`md5`): Add an MD5 checksum to each file.  
- **Binary Content** (`binary_content`): Base64-encodes binary files if forced.  
- **File Size (Human-Readable)** (`filesize_human_readable`): E.g., `14.2 KB`.  

**Create your own** by subclassing `MetadataPlugin`:

```python
# single_file/plugins/metadata/example_plugin.py
from single_file.plugins.metadata.plugin_base import MetadataPlugin

class ExamplePlugin(MetadataPlugin):
    metadata_name = "example_field"
    default = False
    description = "Stores a custom field named 'example_field'."

    def attach_metadata(self, file_info: dict) -> None:
        file_info["example_field"] = "Any custom data you want"
```

Then enable it:

```bash
single-file --metadata-add example_field
```

<br>

---

## VS Code Extension (Coming Soon)

A **Visual Studio Code extension** for SingleFile is in the works. Expect features like:

- **One-Click Flattening**: Consolidate your workspace’s files with minimal effort.  
- **Inline Configuration**: Set paths, formats, and metadata plugins directly in VS Code.  
- **Real-Time Feedback**: See notifications or errors in the VS Code status bar/log.  
- **Auto-Preview**: Open or preview the flattened output in an integrated editor pane.  

Stay tuned for announcements and early previews on the extension’s functionality!

<br>

---

## Contributing & Development

Contributions are encouraged! Here’s how:

1. **Fork** or **clone** this repo.  
2. **Install** in editable mode:
   ```bash
   pip install -e .
   ```
3. **Write** new unit tests in `./tests` (or improve existing ones).  
4. **Run** all tests:
   ```bash
   python -m unittest discover -s tests
   ```
5. **Submit** pull requests to propose features, fix bugs, or enhance documentation.

**Potential Contribution Areas**:

- Additional output plugins (like CSV or a dynamic web viewer).  
- More advanced metadata plugins (code complexity, language detection, etc.).  
- Performance tweaks for scanning large repos.  
- Polishing the user experience (tool tips, CLI help, better error messages).

<br>

---


## License

SingleFile is released under the [MIT License](LICENSE). Feel free to adapt it into your own pipelines or products—credit is greatly appreciated but not mandatory.
