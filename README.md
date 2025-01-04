# SingleFile: Code Flattening Tool

SingleFile is a Python tool that transforms directory structures and their contents into a single, readable document. Inspired by [flatten-codebase](https://github.com/VictorHenrique317/flatten-codebase), this tool has been enhanced to support multiple output formats and improved path handling, making it particularly useful for working with Large Language Models (LLMs) and IDE extensions.

## Primary Use Cases

SingleFile excels in two main scenarios:

1. **LLM Code Analysis**: When working with AI assistants like ChatGPT or Claude, SingleFile helps you prepare your codebase in a format that these models can effectively process. It creates a single document containing both the directory structure and file contents, allowing LLMs to better understand the context and relationships within your code.

2. **VSCode Extension Integration**: The tool's plugin architecture and multiple output formats make it ideal for integration with VSCode extensions. Developers can use SingleFile to create dynamic documentation views, enhance code navigation, or provide better project overviews directly within their IDE.

## Features

SingleFile provides several key capabilities that enhance code analysis and documentation:

- Directory structure visualization with customizable depth
- File content flattening with encoding detection
- Multiple output formats (default, markdown, JSON)
- Configurable directory and file filtering
- Relative and absolute path support
- Plugin architecture for extensibility

## Installation

```bash
git clone https://github.com/yourusername/single-file.git
pip install -e .
