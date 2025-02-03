Below is an **updated `README.md`** that aligns with your **renamed commands (`single-file`)**, **restores** details about the **two-phase CLI** and **mermaid diagram** example, and keeps the **new** sections/examples you provided.

---

![Banner](./images/banner.png)

# SingleFile

SingleFile is a **codebase flattening and analysis** tool designed to unify multiple files and directories into comprehensive, metadata-rich outputs. Whether you need a simple text flatten for a single folder or an in-depth, multi-output, metadata-filled output for AI ingestion, SingleFile’s modular architecture can adapt to your exact requirements.

- **No External Dependencies**: Built exclusively on the Python Standard Library.  
- **Config-Driven**: Merge a JSON config file with CLI arguments for reproducible setups.  
- **Pluggable**: Add your own output/metadata plugins for specialized needs.  

<br>

---
## Acknowledgments

Special thanks to [@VictorHenrique317](https://github.com/VictorHenrique317) for his original work on [flatten-codebase](https://github.com/VictorHenrique317/flatten-codebase.git). SingleFile drew inspiration from flatten-codebase and used it extensively to build this and many related tools.

<br>

---
## Table of Contents

1. [Key Features](#key-features)  
2. [Installation](#installation)  
   - [Linux/macOS](#linuxmacos)  
   - [Windows](#windows)  
   - [Using Pyenv](#using-pyenv)  
3. [Environment Variables](#environment-variables)  
4. [Technical Workflow (Two-Phase CLI)](#technical-workflow-two-phase-cli)  
5. [Basic Usage](#basic-usage)  
   - [A Minimal One-Liner](#a-minimal-one-liner)  
   - [Simple Example with Defaults](#simple-example-with-defaults)  
6. [Intermediate Examples](#intermediate-examples)  
   - [Filtering and Custom Metadata](#filtering-and-custom-metadata)  
   - [Using a JSON Config](#using-a-json-config)  
7. [Advanced Examples](#advanced-examples)  
   - [Multiple Outputs](#multiple-outputs)  
   - [Querying Available Plugins and Configs](#querying-available-plugins-and-configs)  
   - [Mermaid Diagram Example](#mermaid-diagram-example)  
   - [Running from Another Script](#running-from-another-script)  
8. [Plugin Architecture](#plugin-architecture)  
   - [Output Plugins](#output-plugins)  
   - [Metadata Plugins](#metadata-plugins)  
9. [VS Code Extension (Coming Soon)](#vs-code-extension-coming-soon)  
10. [Contributing & Development](#contributing--development)  
11. [License](#license)  

<br>

---

## Key Features

- **Cross-Platform**: Works seamlessly on Windows, macOS, and Linux.  
- **Multiple Output Formats**: Text (`default`), Markdown, and JSON included. Write your own plugin for HTML, CSV, etc.  
- **Rich Metadata**: Default fields like file size, modified date, or extension. Add custom metadata—e.g., MD5 checksums or base64 binary content—through plugins.  
- **Powerful Filtering**: Use regex to include/exclude directories, files, or extensions.  
- **Two-Phase CLI**:
  1. **Phase 1** loads global arguments (like `--config` and `--disable-plugin`).  
  2. **Phase 2** merges your JSON config + plugin-specific flags into the final set of arguments.  
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

## Technical Workflow (Two-Phase CLI)

SingleFile processes its arguments in **two phases**. A quick overview using **Mermaid**:

```mermaid
flowchart TB
    A[Start CLI] --> B((Phase 1))
    B --> C[Parse global args<br/>(--config,<br/>--disable-plugin,<br/>--query,<br/>...)]
    C --> D[Load JSON config (optional)]
    D --> E[Discover and disable<br/>plugins if specified]
    E --> F((Phase 2))
    F --> G[Parse plugin-specific args<br/>& merge final config]
    G --> H[Create CodebaseAnalyzer<br/>and generate outputs]
    H --> I[Done]
```

**Key Points**:
- **Phase 1** loads top-level flags and merges JSON config if provided.  
- **Plugin Discovery**: SingleFile scans for available output/metadata plugins; any disabled plugins are skipped.  
- **Phase 2** merges the config with final CLI flags (including plugin-specific ones like `--md-toc` or `--json-compact`).  
- SingleFile then scans the codebase, collects metadata, and generates output(s).

<br>

---

## Basic Usage

### A Minimal One-Liner

Flatten everything in the current directory into a single text file named `output.txt`:

```bash
single-file
```

**Explanation**:
- Defaults to scanning `.`  
- Uses `--output-file` default of `output`, which the text plugin interprets as `output.txt`  

### Simple Example with Defaults

```bash
single-file \
  --paths ./src \
  --output-file my_project_flat.txt
```

- Scans `./src` recursively with no depth limit.
- Creates one text file: `my_project_flat.txt`.
- **No** advanced filters are applied (default ignore patterns like `.git` still take effect).

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
- Scans `./my_app` **2 levels** deep.
- Excludes `.git` and `__pycache__` directories.
- Only processes `.py` and `.md` files.
- **Adds** MD5 checksums to each file’s metadata (`--metadata-add md5`).
- **Removes** default `size` and `modified` fields from output (`--metadata-remove size modified`).
- Outputs a single file named `my-output.json`.

### Using a JSON Config

```json
// dev_rules.json
{
  "paths": ["./my_app"],
  "exclude_dirs": [".git", "__pycache__"],
  "extensions": ["py", "md", "json"],
  "output_file": "my_app_flat",
  "formats": "markdown"
}
```

Then run:

```bash
single-file --config dev_rules.json --extensions py
```
- Merges settings from `dev_rules.json`.
- CLI override sets `--extensions` to only `.py`.
- Outputs `my_app_flat.md` with code blocks and stats (assuming you also use `--md-stats`).

<br>

---

## Advanced Examples

### Multiple Outputs

```bash
single-file \
  --paths ./my_app \
  --formats default,json \
  --output-file consolidated \
  --ignore-errors
```

- Generates `consolidated.txt` (default text plugin) and `consolidated.json` (JSON plugin).
- **Ignore errors** means any unreadable/permission issues won't crash the process.

### Querying Available Plugins and Configs

```bash
single-file --query formats plugins metadata configs
```

**Returns** (in JSON):
- **formats**: Known output formats (like `default`, `markdown`, `json`).  
- **plugins**: Both output and metadata plugins with descriptions.  
- **metadata**: Default fields and plugin-provided ones (like `md5`, `binary_content`).  
- **configs**: Any config files discovered in `SINGLEFILE_CONFIG_PATH` or `configs/` folder.

### Mermaid Diagram Example

Want a **visual** representation of your directory tree via [Mermaid](https://mermaid-js.github.io/mermaid/)? Create a **custom output** plugin (simplified example):

```python
# single-file/plugins/outputs/mermaid_output.py

from single_file.core import OutputPlugin
from pathlib import Path

class MermaidOutputPlugin(OutputPlugin):
    format_name = "mermaid"
    supported_extensions = [".md"]  # store in a markdown file

    def generate_output(self, output_path: Path) -> None:
        lines = []
        lines.append("```mermaid")
        lines.append("flowchart TB")

        def walk_tree(node, parent_id=None):
            label = node.get("dirpath") or node.get("filepath")
            node_type = node.get("type", "file")
            safe_id = label.replace(".", "_").replace("/", "_")
            lines.append(f'{safe_id}["{label} ({node_type})"]')

            if parent_id:
                lines.append(f"{parent_id} --> {safe_id}")

            if node_type == "directory" and 'children' in node:
                for child in node['children']:
                    walk_tree(child, safe_id)

        walk_tree(self.analyzer.file_tree)
        lines.append("```")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        self.analyzer.logger.info(f"Mermaid diagram generated at {output_path}")
```

Then:

```bash
single-file --formats mermaid --output-file diagram
```

You’ll get a `diagram.md` containing a Mermaid diagram block.

### Running from Another Script

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

<br>

---

## Plugin Architecture

SingleFile is **highly extensible**. You can develop both output plugins (to control how flattened data is written) and metadata plugins (to add fields like checksums or binary data) without modifying the core.

### Output Plugins

Built-in:
- **Default** (`default`, `.txt`): Flatten with text markers around each file’s content.  
- **Markdown** (`markdown`, `.md`): Collapsible sections, table of contents, syntax-highlighted code blocks, etc.  
- **JSON** (`json`, `.json`): A structured JSON representation of your entire codebase.

**Creating Custom Outputs** is as easy as subclassing `OutputPlugin` and implementing `generate_output()`. See the [Mermaid Diagram Example](#mermaid-diagram-example) for a demonstration.

### Metadata Plugins

Common built-ins:
- **MD5** (`md5`): Adds an MD5 checksum for each file.  
- **Binary Content** (`binary_content`): Base64-encode if the file is binary.  
- **File Size (Human-Readable)** (`filesize_human_readable`): E.g., “14.2 KB”.

**Create Your Own** by subclassing `MetadataPlugin`:

```python
# single_file/plugins/metadata/myplugin.py
from single_file.plugins.metadata.plugin_base import MetadataPlugin

class MyCustomPlugin(MetadataPlugin):
    metadata_name = "my_field"
    default = False
    description = "Adds a custom field to each file."

    def attach_metadata(self, file_info: dict) -> None:
        file_info["my_field"] = "Hello from the custom plugin!"
```

Enable with:
```bash
single-file --metadata-add my_field
```
<br>

---

## VS Code Extension (Coming Soon)

A **Visual Studio Code extension** for SingleFile is in the works. Expect features like:

- **One-Click Flattening**: Quickly consolidate your codebase within the editor.  
- **Inline Configuration**: Configure paths, formats, and metadata in VS Code.  
- **Real-Time Feedback**: Warnings, errors, and logs appear in the status bar/log panel.  
- **Auto-Preview**: Open or preview your flattened output directly in an editor pane.

Stay tuned for announcements and early previews on the extension’s functionality!

<br>

---

## Contributing & Development

Contributions are **encouraged**! Here’s how to get started:

1. **Fork** or **clone** this repo.  
2. **Install** in editable mode:
   ```bash
   pip install -e .
   ```
3. **Test** with:
   ```bash
   python -m unittest discover -s tests
   ```
4. Submit **pull requests** to propose features, fix bugs, or enhance docs.

**Potential Contribution Areas**:
- New output plugins (CSV, interactive web viewer, etc.)  
- Advanced metadata plugins (code complexity, language detection)  
- Performance optimizations for large codebases  
- Improved user experience (better CLI error messages, advanced usage docs)

<br>

---

## License

SingleFile is released under the [MIT License](LICENSE). Feel free to adapt it into your own pipelines or products—credit is greatly appreciated but not mandatory.

