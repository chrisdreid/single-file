# single_file_dev01/single_file/singlefile.py

import importlib
import inspect
import sys
from pathlib import Path
from typing import Dict, Type, Set, List
import logging

from single_file.core import OutputPlugin, BaseArguments, FileCollector, DEFAULT_METADATA_FIELDS
from single_file.utils import format_path_for_output

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
        self.disabled_plugins = disabled_plugins or set()
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

        # Load metadata plugins
        self.metadata_plugins = self._discover_metadata_plugins()

        # After file_collector is ready, we can do a separate discover for output if desired,
        # but in this architecture, output plugins are discovered in __main__.py

    def _discover_metadata_plugins(self) -> Dict[str, Type]:
        """
        Dynamically load metadata plugins from single_file/plugins/metadata.
        """
        from single_file.plugins.metadata.plugin_base import MetadataPlugin

        plugins = {}
        metadata_dir = Path(__file__).parent / "plugins" / "metadata"
        if not metadata_dir.exists():
            logger.warning(f"Metadata plugins directory does not exist at {metadata_dir}")
            return plugins

        # Add parent directory to Python path if needed
        project_root = metadata_dir.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        logger.info("Scanning for metadata plugins in: %s", metadata_dir)
        for plugin_file in metadata_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                logger.debug("Skipping private file: %s", plugin_file)
                continue
            try:
                module_name = f"single_file.plugins.metadata.{plugin_file.stem}"
                module = importlib.import_module(module_name)

                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, MetadataPlugin)
                        and obj is not MetadataPlugin
                        and hasattr(obj, "metadata_name")
                    ):
                        plugins[obj.metadata_name] = obj
                        logger.info(f"Loaded metadata plugin: {obj.metadata_name}")

            except Exception as e:
                logger.error(f"Error loading metadata plugin {plugin_file}: {e}")
        return plugins

    def generate_outputs(self) -> None:
        """
        Generate all requested output formats. If --formats is empty or 'default', 
        we do a single output by extension. Otherwise, if user sets multiple 
        formats, we treat the --output-file as a base name and generate one file 
        per format, each with the plugin’s extension.
        """
        output_path = Path(self.args.output_file)
        formats_arg = (self.args.formats or "").strip().lower()

        logger.info(f"Generating outputs for {output_path}")
        logger.info(f"formats_arg = '{formats_arg}'")

        # CASE 1: No explicit --formats or 'default' => single output by extension
        if not formats_arg or formats_arg == "default":
            try:
                chosen_extension = output_path.suffix.lower()
                plugin_cls = self._get_plugin_for_extension(chosen_extension)
                plugin_inst = plugin_cls(self)
                plugin_inst.generate_output(output_path)
                logger.info(f"Generated output using {plugin_cls.format_name} at {output_path}")
            except ValueError as ve:
                logger.error(ve)
            except Exception as e:
                logger.error(f"Error generating output: {e}")

            return

        # CASE 2: Explicit --formats => possibly multiple formats
        requested_formats = [fmt.strip() for fmt in formats_arg.split(",") if fmt.strip()]
        if not requested_formats:
            # If --formats is empty after splitting (e.g. user typed `--formats ,`)
            # fallback to single extension logic:
            try:
                plugin_cls = self._get_plugin_for_extension(output_path.suffix.lower())
                plugin_inst = plugin_cls(self)
                plugin_inst.generate_output(output_path)
            except Exception as e:
                logger.error(f"Error generating fallback output: {e}")
            return

        # If there's exactly one requested format, we can also preserve the extension
        # from --output-file if you'd rather do that. But since you said "if you put
        # formats, then it uses the base of outputfile", let's unify the logic
        # so that a single format is also appended.
        #
        # We'll handle multiple or single the same: treat output_file as a BASE
        # and for each format plugin, append the plugin’s extension.

        # We intentionally strip off any existing extension so we don't get
        # filename.json.json, etc. Then each plugin sets the extension.
        base_name = output_path.with_suffix("")  # removes any existing .ext

        for format_name in requested_formats:
            if format_name not in self.plugins:
                logger.warning(f"No plugin found for format '{format_name}'")
                continue

            plugin_cls = self.plugins[format_name]
            ext = plugin_cls.supported_extensions[0]  # Typically `.json`, `.md`, etc.
            out_path_for_plugin = base_name.with_suffix(ext)

            try:
                plugin_inst = plugin_cls(self)
                plugin_inst.generate_output(out_path_for_plugin)
                logger.info(f"Generated '{format_name}' output => {out_path_for_plugin}")
            except Exception as e:
                logger.error(f"Error generating {format_name} output: {e}")


    def _get_plugin_for_extension(self, extension: str) -> Type[OutputPlugin]:
        """
        Get the appropriate plugin for a file extension, handling multiple matching plugins.
        """
        ext_lower = extension.lower()
        if not ext_lower.startswith('.'):
            ext_lower = '.' + ext_lower

        logger.debug("Looking for plugin for extension: %s", ext_lower)
        logger.debug("Available extensions: %s", list(self.extension_plugin_map.keys()))

        matching_plugins = self.extension_plugin_map.get(ext_lower, [])
        if not matching_plugins:
            raise ValueError(
                f"No plugin available to handle the '{extension}' extension. "
                f"Available plugins support: {', '.join(self.extension_plugin_map.keys())}"
            )

        if len(matching_plugins) == 1:
            return matching_plugins[0]

        # If multiple plugins match, check if a specific format was requested
        if self.args.formats and self.args.formats.lower() != "default":
            requested_formats = [fmt.strip().lower() for fmt in self.args.formats.split(",")]
            for plugin in matching_plugins:
                if plugin.format_name.lower() in requested_formats:
                    return plugin

        # If still ambiguous, raise an error
        plugin_names = [p.format_name for p in matching_plugins]
        raise ValueError(
            f"Multiple plugins ({', '.join(plugin_names)}) can handle the '{extension}' extension. "
            "Please specify which format to use with the --formats argument."
        )

    def analyze_file(self, file_path: Path) -> dict:
        """
        Analyze a single file and cache its information.
        """
        if file_path in self.file_info_cache:
            return self.file_info_cache[file_path]

        try:
            # Step A: gather basic file info
            metadata = self.file_collector.get_file_metadata(file_path)

            # Update stats
            self._update_stats(metadata)

            # Step B: apply incremental metadata logic
            final_fields = set(DEFAULT_METADATA_FIELDS)
            for field in self.args.metadata_remove:
                final_fields.discard(field)
            for field in self.args.metadata_add:
                final_fields.add(field)

            # If user removed certain built-ins:
            if "filepath" not in final_fields:
                # maybe they prefer just 'filename'? Up to you. For now, remove it.
                # We'll keep 'path' internally but can omit from final dict if needed
                pass
            if "extension" not in final_fields and "extension" in metadata:
                metadata.pop("extension", None)
            if "size" not in final_fields and "size" in metadata:
                metadata.pop("size", None)
            if "modified" not in final_fields and "modified" in metadata:
                metadata.pop("modified", None)

            # Step C: Let metadata plugins attach their fields
            for plugin_name, plugin_cls in self.metadata_plugins.items():
                if plugin_name in final_fields:
                    plugin_instance = plugin_cls()
                    plugin_instance.attach_metadata(metadata)

            # Cache
            self.file_info_cache[file_path] = metadata
            return metadata

        except Exception as e:
            if not self.args.ignore_errors:
                raise
            logger.warning(f"Could not analyze {file_path}: {e}")
            return {}

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
