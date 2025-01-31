# single_file_dev01/tests/test_plugins.py

import unittest
from pathlib import Path
import shutil
import os
import json
import sys
import importlib
import inspect

from typing import Set, Dict, Type
from single_file.core import BaseArguments, OutputPlugin
from single_file.singlefile import CodebaseAnalyzer

# If your test references 'json_extended_output.py' or 'json_basic_output.py', 
# remove or adapt them if they're no longer present.

def discover_output_plugins(disabled_plugins: Set[str]) -> Dict[str, Type[OutputPlugin]]:
    """
    A test helper to discover output plugins in the new outputs/ directory.
    """
    plugins = {}
    plugins_dir = Path(__file__).parent.parent / "single_file" / "plugins" / "outputs"

    if not plugins_dir.exists():
        return plugins

    project_root = plugins_dir.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    for plugin_file in plugins_dir.glob("*.py"):
        if plugin_file.name.startswith("_"):
            continue
        try:
            module_name = f"single_file.plugins.outputs.{plugin_file.stem}"
            module = importlib.import_module(module_name)

            for name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, OutputPlugin)
                    and obj is not OutputPlugin
                    and obj.format_name
                    and hasattr(obj, "supported_extensions")
                    and obj.supported_extensions
                ):
                    if obj.format_name in disabled_plugins:
                        continue
                    plugins[obj.format_name] = obj
        except Exception:
            continue

    return plugins


class TestPlugins(unittest.TestCase):
    def setUp(self):
        args = BaseArguments()
        args.paths = [Path(".")]
        args.output_file = "test_output/output.json"
        args.formats = "json,markdown"
        args.ignore_errors = True
        args.depth = 1
        args.absolute_paths = False
        args.extensions = ["py", "md"]
        args.exclude_extensions = []
        args.exclude_dirs = [r"^\.git$", r"^__pycache__$"]
        args.exclude_files = [r".*\.log$"]
        args.include_dirs = []
        args.include_files = []
        args.show_guide = False
        args.replace_invalid_chars = True
        disabled_plugins = set()

        self.analyzer = CodebaseAnalyzer(args, disabled_plugins)

        # Ensure test_output directory is clean
        os.makedirs("test_output", exist_ok=True)
        for f in Path("test_output").glob("*"):
            if f.is_file():
                f.unlink()

    def tearDown(self):
        shutil.rmtree("test_output", ignore_errors=True)

    def test_plugin_discovery(self):
        disabled_plugins = set()
        discovered = discover_output_plugins(disabled_plugins)
        # Should find 'json' and 'markdown', etc.
        self.assertIn('json', discovered)
        self.assertIn('markdown', discovered)

    def test_json_output_plugin(self):
        # Manually load the JSON plugin and test generate_output
        from single_file.plugins.outputs.json_output import JSONOutputPlugin
        plugin = JSONOutputPlugin(self.analyzer)
        output_path = Path("test_output") / "codebase.json"
        plugin.generate_output(output_path)
        self.assertTrue(output_path.exists())

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("metadata", data)
            self.assertIn("files", data)

    def test_markdown_output_plugin(self):
        from single_file.plugins.outputs.markdown_output import MarkdownOutputPlugin
        plugin = MarkdownOutputPlugin(self.analyzer)
        output_path = Path("test_output") / "codebase.md"
        plugin.generate_output(output_path)
        self.assertTrue(output_path.exists())

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("# Codebase Documentation", content)
            self.assertIn("## Files", content)


if __name__ == "__main__":
    unittest.main()
