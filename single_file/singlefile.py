# single_file_dev01/single_file/singlefile.py

import importlib
import inspect
import sys
from pathlib import Path
from typing import Dict, Type, Set, List
import logging

from single_file.core import OutputPlugin, BaseArguments, FileCollector

logger = logging.getLogger(__name__)


class CodebaseAnalyzer:
    """
    Main class for analyzing codebases and coordinating output generation.
    """

    def __init__(self, args: BaseArguments, disabled_plugins: Set[str] = None):
        """
        Initialize the analyzer with arguments and set up necessary components.

        Args:
            args: BaseArguments instance containing configuration
            disabled_plugins: Set of plugin names to disable
        """
        self.args = args
        self.file_info_cache: Dict[Path, dict] = {}
        self.plugins: Dict[str, Type[OutputPlugin]] = {}
        self.stats = {
            "total_files": 0,
            "total_size": 0,
            "extensions": {},
            "largest_files": [],
            "recently_modified": [],
        }

        # Initialize file collector BEFORE loading plugins
        self.file_collector = FileCollector(self)

        # Load plugins after file collector is initialized
        self._load_plugins(disabled_plugins or set())

    def _load_plugins(self, disabled_plugins: Set[str]) -> None:
        """
        Dynamically load output plugins from the plugins directory, excluding disabled ones.

        Args:
            disabled_plugins: Set of plugin names to disable
        """
        plugins_dir = Path(__file__).parent / "plugins"
        if not plugins_dir.exists():
            logger.warning(f"Plugins directory does not exist at {plugins_dir}")
            return

        # Add parent directory to Python path if needed
        project_root = plugins_dir.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        # Import each Python file in the plugins directory
        for plugin_file in plugins_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue

            try:
                # Import using absolute import
                module_name = f"single_file.plugins.{plugin_file.stem}"
                module = importlib.import_module(module_name)

                # Find all OutputPlugin subclasses in the module
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
                            logger.info(
                                f"Plugin '{obj.format_name}' is disabled and will not be loaded."
                            )
                            continue
                        self.plugins[obj.format_name] = obj
                        logger.info(f"Loaded plugin for format: {obj.format_name}")
            except Exception as e:
                logger.error(f"Error loading plugin {plugin_file}: {e}")

        # After loading all plugins, build the extension-to-plugin mapping
        self.extension_plugin_map: Dict[str, List[Type[OutputPlugin]]] = {}
        for plugin in self.plugins.values():
            for ext in plugin.supported_extensions:
                ext_lower = ext.lower()
                if ext_lower not in self.extension_plugin_map:
                    self.extension_plugin_map[ext_lower] = []
                self.extension_plugin_map[ext_lower].append(plugin)

    def analyze_file(self, file_path: Path) -> dict:
        """
        Analyze a single file and cache its information.

        Args:
            file_path: Path to the file to analyze

        Returns:
            dict: File metadata and analysis results
        """
        if file_path in self.file_info_cache:
            return self.file_info_cache[file_path]

        try:
            metadata = self.file_collector.get_file_metadata(file_path)
            self._update_stats(metadata)
            self.file_info_cache[file_path] = metadata
            return metadata

        except Exception as e:
            if not self.args.ignore_errors:
                raise
            logger.warning(f"Could not analyze {file_path}: {e}")
            return None

    def generate_outputs(self) -> None:
        """
        Generate all requested output formats using appropriate plugins.
        """
        output_path = Path(self.args.output_file)
        output_extension = output_path.suffix.lower()

        # If the user specified multiple formats, handle each accordingly
        if self.args.formats:
            requested_formats = [fmt.strip().lower() for fmt in self.args.formats.split(",")]
            for format_name in requested_formats:
                if format_name not in self.plugins:
                    logger.warning(f"No plugin found for format '{format_name}'")
                    continue
                try:
                    plugin = self.plugins[format_name](self)
                    # Determine the actual extension based on the plugin's supported extensions
                    # For simplicity, we use the first supported extension
                    ext = plugin.supported_extensions[0]
                    formatted_output_path = output_path.with_suffix(ext)
                    plugin.generate_output(formatted_output_path)
                    logger.info(f"Generated {format_name} output at {formatted_output_path}")
                except Exception as e:
                    logger.error(f"Error generating {format_name} output: {e}")
        else:
            # Default behavior: use the output file's extension to select the plugin
            try:
                plugin = self.get_plugin_for_extension(output_extension)
                plugin_instance = plugin(self)
                plugin_instance.generate_output(output_path)
                logger.info(f"Generated output at {output_path} using plugin '{plugin.format_name}'")
            except ValueError as ve:
                logger.error(ve)
            except Exception as e:
                logger.error(f"Error generating output: {e}")

    def get_plugin_for_extension(self, extension: str) -> Type[OutputPlugin]:
        """
        Retrieve the appropriate plugin for a given file extension.

        Args:
            extension: The file extension (e.g., '.json')

        Returns:
            OutputPlugin class that handles the extension

        Raises:
            ValueError: If no plugin or multiple plugins are found for the extension
        """
        ext_lower = extension.lower()
        plugins = self.extension_plugin_map.get(ext_lower, [])

        if not plugins:
            raise ValueError(f"No plugin available to handle the '{extension}' format.")

        if len(plugins) > 1:
            raise ValueError(
                f"Multiple plugins available to handle the '{extension}' format. "
                f"Please specify which one to use."
            )

        return plugins[0]

    def _update_stats(self, file_info: dict) -> None:
        """
        Update the statistics with information from a new file.

        Args:
            file_info: Dictionary containing file information
        """
        self.stats["total_files"] += 1
        self.stats["total_size"] += file_info["size"]

        ext = file_info["extension"]
        self.stats["extensions"][ext] = self.stats["extensions"].get(ext, 0) + 1

        # Update largest files list
        self.stats["largest_files"].append((file_info["path"], file_info["size"]))
        self.stats["largest_files"].sort(key=lambda x: x[1], reverse=True)
        self.stats["largest_files"] = self.stats["largest_files"][:10]

        # Update recently modified list
        self.stats["recently_modified"].append((file_info["path"], file_info["modified"]))
        self.stats["recently_modified"].sort(key=lambda x: x[1], reverse=True)
        self.stats["recently_modified"] = self.stats["recently_modified"][:10]
