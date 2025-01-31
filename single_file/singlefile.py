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
        self.extension_plugin_map: Dict[str, List[Type[OutputPlugin]]] = {}
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

        logger.info("Scanning for plugins in: %s", plugins_dir)
        # Import each Python file in the plugins directory
        for plugin_file in plugins_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                logger.debug("Skipping private file: %s", plugin_file)
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

                        # Build extension-to-plugin mapping
                        for ext in obj.supported_extensions:
                            # Normalize extension format (ensure it starts with dot)
                            ext_lower = ext.lower()
                            if not ext_lower.startswith('.'):
                                ext_lower = '.' + ext_lower
                            if ext_lower not in self.extension_plugin_map:
                                self.extension_plugin_map[ext_lower] = []
                            self.extension_plugin_map[ext_lower].append(obj)
                            logger.debug("Mapped extension %s to plugin %s", ext_lower, obj.format_name)

            except Exception as e:
                logger.error(f"Error loading plugin {plugin_file}: {e}")

    def generate_outputs(self) -> None:
        """
        Generate all requested output formats using appropriate plugins.
        """
        output_path = Path(self.args.output_file)
        output_extension = output_path.suffix.lower()
        
        logger.info("Generating output for path: %s", output_path)
        logger.info("Detected extension: %s", output_extension)
        logger.info("Available plugins: %s", list(self.plugins.keys()))
        logger.info("Mapped extensions: %s", list(self.extension_plugin_map.keys()))

        # If the user specified multiple formats, handle each accordingly
        if self.args.formats and self.args.formats.lower() != "default":
            requested_formats = [fmt.strip().lower() for fmt in self.args.formats.split(",")]
            for format_name in requested_formats:
                if format_name not in self.plugins:
                    logger.warning(f"No plugin found for format '{format_name}'")
                    continue
                try:
                    plugin = self.plugins[format_name]
                    # Use the first supported extension from the plugin
                    ext = plugin.supported_extensions[0]
                    formatted_output_path = output_path.with_suffix(ext)
                    plugin(self).generate_output(formatted_output_path)
                    logger.info(f"Generated {format_name} output at {formatted_output_path}")
                except Exception as e:
                    logger.error(f"Error generating {format_name} output: {e}")
        else:
            # Use the output file's extension to select the plugin
            try:
                plugin = self._get_plugin_for_extension(output_extension)
                plugin(self).generate_output(output_path)
                logger.info(f"Generated output at {output_path}")
            except ValueError as ve:
                logger.error(ve)
            except Exception as e:
                logger.error(f"Error generating output: {e}")

    def _get_plugin_for_extension(self, extension: str) -> Type[OutputPlugin]:
        """
        Get the appropriate plugin for a file extension, handling multiple matching plugins.

        Args:
            extension: The file extension (with or without leading dot)

        Returns:
            OutputPlugin class that handles the extension

        Raises:
            ValueError: If no plugin is found or if multiple plugins match without a format specified
        """
        # Normalize the extension (ensure it starts with dot and convert to lowercase)
        ext_lower = extension.lower()
        if not ext_lower.startswith('.'):
            ext_lower = '.' + ext_lower

        logger.debug("Looking for plugin for extension: %s", ext_lower)
        logger.debug("Available extensions: %s", list(self.extension_plugin_map.keys()))
        
        # Get all plugins that support this extension
        matching_plugins = self.extension_plugin_map.get(ext_lower, [])

        if not matching_plugins:
            raise ValueError(
                f"No plugin available to handle the '{extension}' extension. "
                f"Available plugins support: {', '.join(self.extension_plugin_map.keys())}"
            )

        if len(matching_plugins) == 1:
            return matching_plugins[0]

        # Multiple plugins match - check if a specific format was requested
        if self.args.formats and self.args.formats.lower() != "default":
            requested_formats = [fmt.strip().lower() for fmt in self.args.formats.split(",")]
            for plugin in matching_plugins:
                if plugin.format_name.lower() in requested_formats:
                    return plugin

        # Multiple plugins match but no specific format was requested
        plugin_names = [p.format_name for p in matching_plugins]
        raise ValueError(
            f"Multiple plugins ({', '.join(plugin_names)}) can handle the '{extension}' extension. "
            "Please specify which format to use with the --formats argument."
        )

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

    def _update_stats(self, file_info: dict) -> None:
        """Update the statistics with information from a new file."""
        self.stats["total_files"] += 1
        self.stats["total_size"] += file_info["size"]

        ext = file_info["extension"]
        self.stats["extensions"][ext] = self.stats["extensions"].get(ext, 0) + 1

        self.stats["largest_files"].append((file_info["path"], file_info["size"]))
        self.stats["largest_files"].sort(key=lambda x: x[1], reverse=True)
        self.stats["largest_files"] = self.stats["largest_files"][:10]

        self.stats["recently_modified"].append((file_info["path"], file_info["modified"]))
        self.stats["recently_modified"].sort(key=lambda x: x[1], reverse=True)
        self.stats["recently_modified"] = self.stats["recently_modified"][:10]