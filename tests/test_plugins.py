# single_file_dev01/tests/test_plugins.py

import unittest
from pathlib import Path
from single_file.singlefile import CodebaseAnalyzer
from single_file.core import BaseArguments
from single_file.plugins.json_basic_output import JSONBasicOutputPlugin
from single_file.plugins.json_extended_output import JSONExtendedOutputPlugin
from single_file.plugins.markdown_output import MarkdownOutputPlugin
import shutil
import os
import json


class TestPlugins(unittest.TestCase):
    def setUp(self):
        # Setup with default arguments
        args = BaseArguments()
        args.paths = [Path(".")]
        args.output_file = "test_output/output.json"
        args.formats = "json_basic,json_extended,markdown"
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

        # Ensure test_output directory exists and is clean
        os.makedirs("test_output", exist_ok=True)
        for f in Path("test_output").glob("*"):
            if f.is_file():
                f.unlink()

    def tearDown(self):
        # Clean up test_output directory after tests
        shutil.rmtree("test_output", ignore_errors=True)

    def test_json_basic_output_plugin(self):
        # Test JSON Basic output generation
        json_basic_plugin = JSONBasicOutputPlugin(self.analyzer)
        output_path = Path("test_output") / "codebase.json"
        json_basic_plugin.generate_output(output_path)
        self.assertTrue(output_path.exists(), "JSON Basic output file was not created")

        # Check JSON content structure
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("path", data, "JSON Basic output missing 'path' key")
            self.assertIn("files", data, "JSON Basic output missing 'files' key")

    def test_json_extended_output_plugin(self):
        # Test JSON Extended output generation
        json_extended_plugin = JSONExtendedOutputPlugin(self.analyzer)
        output_path = Path("test_output") / "codebase.json"
        json_extended_plugin.generate_output(output_path)
        self.assertTrue(output_path.exists(), "JSON Extended output file was not created")

        # Check JSON content structure
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("metadata", data, "JSON Extended output missing 'metadata' key")

    def test_markdown_output_plugin(self):
        # Test Markdown output generation
        md_plugin = MarkdownOutputPlugin(self.analyzer)
        output_path = Path("test_output") / "codebase.md"
        md_plugin.generate_output(output_path)
        self.assertTrue(output_path.exists(), "Markdown output file was not created")

        # Check Markdown content structure
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("# Codebase Documentation", content, "Markdown output missing header")
            self.assertIn("## Files", content, "Markdown output missing 'Files' section")

    def test_plugin_selection(self):
        # Test selecting a specific plugin when multiple plugins handle the same extension
        args = BaseArguments()
        args.paths = [Path(".")]
        args.output_file = "test_output/output.json"
        args.formats = "json_basic,json_extended"
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

        # Initialize CodebaseAnalyzer with the desired plugin
        analyzer = CodebaseAnalyzer(args, disabled_plugins)
        analyzer.plugins = discover_plugins(disabled_plugins)

        # Manually select the json_extended plugin
        selected_plugin = analyzer.plugins.get("json_extended")
        self.assertIsNotNone(selected_plugin, "json_extended plugin should be loaded")

        # Generate output using the selected plugin
        plugin_instance = selected_plugin(analyzer)
        plugin_instance.generate_output(analyzer.args.output_file)

        # Verify output file exists
        self.assertTrue(
            Path(analyzer.args.output_file).exists(),
            "JSON Extended output file was not created",
        )

        # Verify metadata is present
        with open(analyzer.args.output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("metadata", data, "JSON Extended output missing 'metadata' key")


def discover_plugins(disabled_plugins: Set[str]) -> Dict[str, Type[OutputPlugin]]:
    """
    Discover and load output plugins from the plugins directory, excluding disabled ones.

    Args:
        disabled_plugins: Set of plugin names to disable

    Returns:
        Dict mapping format_name to OutputPlugin class
    """
    plugins = {}
    plugins_dir = Path(__file__).parent.parent / "single_file" / "plugins"

    if not plugins_dir.exists():
        return plugins

    project_root = plugins_dir.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    for plugin_file in plugins_dir.glob("*.py"):
        if plugin_file.name.startswith("_"):
            continue

        try:
            module_name = f"single_file.plugins.{plugin_file.stem}"
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


if __name__ == "__main__":
    unittest.main()
