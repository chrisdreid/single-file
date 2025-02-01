#!/usr/bin/env python
"""
Main entry point for SingleFile.
This module parses arguments, loads configuration, discovers plugins,
and runs the analyzer to gather file metadata and build a raw file tree.
Output plugins then format this data into their desired output format.
"""

import sys
import argparse
import traceback
import json
import logging
import importlib
import inspect
import os
from pathlib import Path
from typing import Type, Set, Dict

from single_file.core import OutputPlugin, BaseArguments, FileCollector, DEFAULT_METADATA_FIELDS
from single_file.utils import format_path_for_output

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def discover_plugins(disabled_plugins: Set[str]) -> Dict[str, Type[OutputPlugin]]:
    """
    Discover and load output plugins from the plugins directory, excluding those disabled.
    The plugins are located in "plugins/outputs" relative to this file.
    """
    plugins_dict = {}
    plugins_dir = Path(__file__).parent / "plugins" / "outputs"
    if not plugins_dir.exists():
        logger.warning(f"Output plugins directory does not exist at {plugins_dir}")
        return plugins_dict

    project_root = plugins_dir.parent  # relative to single_file/
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    for plugin_file in plugins_dir.glob("*.py"):
        if plugin_file.name.startswith("_"):
            continue
        try:
            module_name = f"single_file.plugins.outputs.{plugin_file.stem}"
            plugin_module = importlib.import_module(module_name)
            for member_name, member_obj in inspect.getmembers(plugin_module):
                if (inspect.isclass(member_obj)
                        and issubclass(member_obj, OutputPlugin)
                        and member_obj is not OutputPlugin
                        and member_obj.format_name):
                    if member_obj.format_name in disabled_plugins:
                        logger.info(f"Plugin '{member_obj.format_name}' is disabled.")
                        continue
                    plugins_dict[member_obj.format_name] = member_obj
                    logger.info(f"Loaded plugin for format: {member_obj.format_name}")
        except Exception as import_err:
            logger.error(f"Error loading plugin {plugin_file}: {import_err}")
    return plugins_dict


class CodebaseAnalyzer:
    """
    Main class for analyzing codebases and coordinating output generation.
    Gathers all file metadata and builds a raw file tree (a nested dict) which is then
    available to the output plugins.
    """
    def __init__(self, args: BaseArguments, disabled_plugins: Set[str] = None):
        self.args = args
        self.disabled_plugins = disabled_plugins or set()
        self.file_info_cache: Dict[Path, dict] = {}
        self.plugins: Dict[str, Type[OutputPlugin]] = {}
        self.stats = {
            "total_files": 0,
            "total_size": 0,
            "extensions": {},
            "largest_files": [],
            "recently_modified": [],
        }
        self.logger = logging.getLogger(__name__)  # now available for plugins
        self.file_collector = FileCollector(self)
        self.metadata_plugins = self._discover_metadata_plugins()
        self.file_tree = {}  # Will be populated with the raw file tree

    def _discover_metadata_plugins(self) -> Dict[str, Type]:
        from single_file.plugins.metadata.plugin_base import MetadataPlugin
        plugins = {}
        metadata_dir = Path(__file__).parent / "plugins" / "metadata"
        if not metadata_dir.exists():
            logger.warning(f"Metadata plugins directory does not exist at {metadata_dir}")
            return plugins
        project_root = metadata_dir.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        logger.info("Scanning for metadata plugins in: %s", metadata_dir)
        for plugin_file in metadata_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            try:
                module_name = f"single_file.plugins.metadata.{plugin_file.stem}"
                module = importlib.import_module(module_name)
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj)
                            and issubclass(obj, MetadataPlugin)
                            and obj is not MetadataPlugin
                            and hasattr(obj, "metadata_name")):
                        plugins[obj.metadata_name] = obj
                        logger.info(f"Loaded metadata plugin: {obj.metadata_name}")
            except Exception as e:
                logger.error(f"Error loading metadata plugin {plugin_file}: {e}")
        return plugins

    def gather_all_files(self) -> None:
        """
        Walk through each input path, build the raw file tree,
        and populate the file_info_cache by analyzing each file.
        """
        trees = []
        for input_path in self.args.paths:
            p_obj = Path(input_path).resolve()
            if p_obj.exists():
                if p_obj.is_dir():
                    tree = self.file_collector.build_file_tree(p_obj)
                    trees.append(tree)
                    for file in self.file_collector.collect_files(p_obj):
                        self.analyze_file(file)
                elif p_obj.is_file():
                    self.analyze_file(p_obj)
                    trees.append({
                        "name": p_obj.name,
                        "path": str(p_obj),
                        "type": "file",
                        "metadata": self.file_info_cache.get(p_obj)
                    })
        if len(trees) == 1:
            self.file_tree = trees[0]
        else:
            self.file_tree = {"name": "root", "path": "", "type": "directory", "children": trees}

    def generate_outputs(self) -> None:
        """
        Generate output files based on the specified formats.
        The file tree and file metadata are gathered once and then
        passed to each output plugin for formatting.
        """
        self.gather_all_files()
        output_path = Path(self.args.output_file)
        formats_arg = (self.args.formats or "").strip().lower()
        logger.info(f"Generating outputs for {output_path}")
        logger.info(f"formats_arg = '{formats_arg}'")

        if not formats_arg or formats_arg == "default":
            try:
                chosen_extension = output_path.suffix.lower()
                for plugin in self.plugins.values():
                    if chosen_extension in plugin.supported_extensions:
                        plugin_inst = plugin(self)
                        plugin_inst.generate_output(output_path)
                        logger.info(f"Generated output using {plugin.format_name} at {output_path}")
                        break
                else:
                    raise ValueError(f"No plugin available for extension '{chosen_extension}'.")
            except Exception as e:
                logger.error(f"Error generating default output: {e}")
            return

        requested_formats = [fmt.strip() for fmt in formats_arg.split(",") if fmt.strip()]
        base_name = output_path.with_suffix("")
        for format_name in requested_formats:
            if format_name not in self.plugins:
                logger.warning(f"No plugin found for format '{format_name}'")
                continue
            plugin_cls = self.plugins[format_name]
            ext = plugin_cls.supported_extensions[0]
            out_path_for_plugin = base_name.with_suffix(ext)
            try:
                plugin_inst = plugin_cls(self)
                plugin_inst.generate_output(out_path_for_plugin)
                logger.info(f"Generated '{format_name}' output => {out_path_for_plugin}")
            except Exception as e:
                logger.error(f"Error generating {format_name} output: {e}")

    def analyze_file(self, file_path: Path) -> dict:
        if file_path in self.file_info_cache:
            return self.file_info_cache[file_path]
        try:
            # Step 1: Gather basic metadata from the file.
            metadata = self.file_collector.get_file_metadata(file_path)
            self._update_stats(metadata)
            
            # Step 2: Start with the default set of metadata keys.
            final_fields = set(DEFAULT_METADATA_FIELDS)  # e.g., {"filepath", "size", "modified", "extension"}
            
            # Remove any keys the user wants removed.
            for field in self.args.metadata_remove:
                final_fields.discard(field)
            
            # Add any extra fields requested.
            for field in self.args.metadata_add:
                final_fields.add(field)
            
            # Step 3: Let metadata plugins attach their fields (if their plugin name is in final_fields).
            for plugin_name, plugin_cls in self.metadata_plugins.items():
                if plugin_name in final_fields:
                    plugin_instance = plugin_cls()
                    plugin_instance.attach_metadata(metadata)
            
            # Step 4: Remove default metadata keys that are not allowed by final_fields.
            for key in list(metadata.keys()):
                if key in DEFAULT_METADATA_FIELDS and key not in final_fields:
                    del metadata[key]
            
            self.file_info_cache[file_path] = metadata
            return metadata

        except Exception as e:
            if not self.args.ignore_errors:
                raise
            self.logger.warning(f"Could not analyze {file_path}: {e}")
            return {}


    def _update_stats(self, file_info: dict) -> None:
        self.stats["total_files"] += 1
        self.stats["total_size"] += file_info["size"]
        ext = file_info["extension"]
        self.stats["extensions"][ext] = self.stats["extensions"].get(ext, 0) + 1
        # Use the 'filepath' field instead of 'path'
        self.stats["largest_files"].append((file_info["filepath"], file_info["size"]))
        self.stats["largest_files"].sort(key=lambda x: x[1], reverse=True)
        self.stats["largest_files"] = self.stats["largest_files"][:10]
        self.stats["recently_modified"].append((file_info["filepath"], file_info["modified"]))
        self.stats["recently_modified"].sort(key=lambda x: x[1], reverse=True)
        self.stats["recently_modified"] = self.stats["recently_modified"][:10]


def main(cli_args=None):
    if cli_args is None:
        cli_args = sys.argv[1:]
    phase1_parser = argparse.ArgumentParser(add_help=False)
    BaseArguments.add_core_arguments(phase1_parser)
    phase1_parser.add_argument("--config", default=None, help="Path to a JSON config file")
    phase1_parser.add_argument("--disable-plugin", nargs="*", default=[], help="Disable plugins")
    phase1_parser.add_argument("--query", nargs="+", default=None, help="Query available items")
    phase1_args, remaining_args = phase1_parser.parse_known_args(cli_args)
    
    # Merge configuration file if provided
    if phase1_args.config:
        config_path = Path(phase1_args.config)
        if config_path.is_file():
            with open(config_path, "r", encoding="utf-8") as config_handle:
                config_data = json.load(config_handle)
            for key, value in config_data.items():
                if hasattr(phase1_args, key):
                    setattr(phase1_args, key, value)
    logger.info("Phase 1 arguments:")
    for arg_key in vars(phase1_args):
        logger.info(f"  {arg_key} => {getattr(phase1_args, arg_key)}")
    
    disabled_plugin_set = set(phase1_args.disable_plugin)
    active_plugins = discover_plugins(disabled_plugin_set)
    phase2_parser = argparse.ArgumentParser(parents=[phase1_parser], add_help=False)
    for plugin_class in active_plugins.values():
        plugin_class.add_arguments(phase2_parser)
    phase2_parser.add_argument("-h", "--help", action="help", help="Show help message")
    final_args = phase2_parser.parse_args(cli_args)
    actual_args = BaseArguments.from_namespace(final_args)
    
    analyzer = CodebaseAnalyzer(actual_args, disabled_plugin_set)
    analyzer.plugins = active_plugins
    # Optional: Map plugin names from supported_extensions for convenience.
    for plugin_class in active_plugins.values():
        analyzer.plugins[plugin_class.format_name] = plugin_class

    if actual_args.query:
        query_summary = {"formats": list(active_plugins.keys())}
        print(json.dumps(query_summary, indent=2))
        return 0

    try:
        analyzer.generate_outputs()
    except Exception as gen_err:
        logger.error(f"Error during execution: {gen_err}")
        traceback.print_exc()
        sys.exit(1)
    return 0

if __name__ == "__main__":
    sys.exit(main())
