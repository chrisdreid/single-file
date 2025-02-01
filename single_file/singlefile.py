#!/usr/bin/env python
"""
Main entry point for SingleFile.
This module parses arguments, loads configuration, discovers plugins,
builds the dynamic metadata configuration, and runs the analyzer.
"""

import sys
import argparse
import traceback
import json
import logging
import importlib
import inspect
from pathlib import Path
from typing import Set, Dict, Type

from single_file.core import OutputPlugin, BaseArguments, FileCollector, BUILTIN_METADATA
from single_file.utils import format_path_for_output

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# --- Dynamic Metadata Configuration and Analyzer ---

class CodebaseAnalyzer:
    """
    Main class for analyzing codebases and coordinating output generation.
    It gathers file metadata (as a flat dictionary) and builds a raw file tree.
    It also builds a dynamic metadata configuration by merging built-in keys with
    keys provided by loaded metadata plugins.
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
        self.logger = logging.getLogger(__name__)
        self.file_collector = FileCollector(self)
        self.metadata_plugins = self._discover_metadata_plugins()
        self.build_dynamic_metadata_config()
        self.file_tree = {}  # Will be set by gather_all_files()

    def build_dynamic_metadata_config(self):
        config = BUILTIN_METADATA.copy()
        for plugin in self.metadata_plugins.values():
            key = plugin.metadata_name
            default_value = getattr(plugin, "default", False)
            description = getattr(plugin, "description", "")
            config[key] = {"default": default_value, "description": description}
        self.metadata_config = config

    def _discover_metadata_plugins(self) -> Dict[str, Type]:
        from single_file.plugins.metadata.plugin_base import MetadataPlugin
        plugins = {}
        metadata_dir = Path(__file__).parent / "plugins" / "metadata"
        if not metadata_dir.exists():
            self.logger.warning(f"Metadata plugins directory does not exist at {metadata_dir}")
            return plugins
        project_root = metadata_dir.parent
        import sys
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        self.logger.info("Scanning for metadata plugins in: %s", metadata_dir)
        for plugin_file in metadata_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            try:
                module_name = f"single_file.plugins.metadata.{plugin_file.stem}"
                module = importlib.import_module(module_name)
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and issubclass(obj, MetadataPlugin)
                            and obj is not MetadataPlugin and hasattr(obj, "metadata_name")):
                        plugins[obj.metadata_name] = obj
                        self.logger.info(f"Loaded metadata plugin: {obj.metadata_name}")
            except Exception as e:
                self.logger.error(f"Error loading metadata plugin {plugin_file}: {e}")
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
                        "filepath": str(p_obj.resolve()),
                        "type": "file"
                    })
        if len(trees) == 1:
            self.file_tree = trees[0]
        else:
            self.file_tree = {"filepath": "root", "type": "directory", "children": trees}

    def analyze_dir(self, dir_path: Path) -> dict:
        try:
            metadata = self.file_collector.get_dir_metadata(dir_path)
            metadata["type"] = "directory"
            # For directories, we might want to add a 'dirpath' key instead of 'filepath'.
            # (No size, content, etc., for directories by default.)
            allowed = {k for k, cfg in self.metadata_config.items() if cfg["default"]}
            for key in self.args.metadata_remove:
                allowed.discard(key)
            for key in self.args.metadata_add:
                allowed.add(key)
            filtered = {k: v for k, v in metadata.items() if k not in self.metadata_config or k in allowed}
            for plugin_name, plugin_cls in self.metadata_plugins.items():
                if plugin_name in allowed:
                    plugin_instance = plugin_cls(analyzer=self)
                    plugin_instance.attach_metadata(filtered)
            return filtered
        except Exception as e:
            if not self.args.ignore_errors:
                raise
            self.logger.warning(f"Could not analyze directory {dir_path}: {e}")
            return {}
        
    def analyze_file(self, file_path: Path) -> dict:
        if file_path in self.file_info_cache:
            return self.file_info_cache[file_path]
        try:
            # Gather all available metadata.
            metadata = self.file_collector.get_file_metadata(file_path)
            self._update_stats(metadata)
            # (For files, do not set "entry_type"; we will use "type" if the user enables it.)
            
            # Compute allowed keys dynamically.
            allowed = {k for k, cfg in self.metadata_config.items() if cfg["default"]}
            for key in self.args.metadata_remove:
                allowed.discard(key)
            for key in self.args.metadata_add:
                allowed.add(key)
            
            # If the user requested "type" in the output, set it for files.
            if "type" in allowed:
                metadata["type"] = "file"
            
            # Filter metadata: only keep keys that are either not in metadata_config or are allowed.
            filtered = {k: v for k, v in metadata.items() if k not in self.metadata_config or k in allowed}
            
            # Now, for each metadata plugin whose key is allowed, attach its metadata.
            for plugin_name, plugin_cls in self.metadata_plugins.items():
                if plugin_name in allowed:
                    plugin_instance = plugin_cls(analyzer=self)
                    plugin_instance.attach_metadata(filtered)
            
            self.file_info_cache[file_path] = filtered
            return filtered
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
        self.stats["largest_files"].append((file_info["filepath"], file_info["size"]))
        self.stats["largest_files"].sort(key=lambda x: x[1], reverse=True)
        self.stats["largest_files"] = self.stats["largest_files"][:10]
        self.stats["recently_modified"].append((file_info["filepath"], file_info["modified"]))
        self.stats["recently_modified"].sort(key=lambda x: x[1], reverse=True)
        self.stats["recently_modified"] = self.stats["recently_modified"][:10]
        

    def generate_outputs(self) -> None:
        """
        Generate output files based on the specified formats.
        """
        self.gather_all_files()
        output_path = Path(self.args.output_file)
        formats_arg = (self.args.formats or "").strip().lower()
        self.logger.info(f"Generating outputs for {output_path}")
        self.logger.info(f"formats_arg = '{formats_arg}'")

        if not formats_arg or formats_arg == "default":
            try:
                chosen_extension = output_path.suffix.lower()
                for plugin in self.plugins.values():
                    if chosen_extension in plugin.supported_extensions:
                        plugin_inst = plugin(self)
                        plugin_inst.generate_output(output_path)
                        self.logger.info(f"Generated output using {plugin.format_name} at {output_path}")
                        break
                else:
                    raise ValueError(f"No plugin available for extension '{chosen_extension}'.")
            except Exception as e:
                self.logger.error(f"Error generating default output: {e}")
            return

        requested_formats = [fmt.strip() for fmt in formats_arg.split(",") if fmt.strip()]
        base_name = output_path.with_suffix("")
        for format_name in requested_formats:
            if format_name not in self.plugins:
                self.logger.warning(f"No plugin found for format '{format_name}'")
                continue
            plugin_cls = self.plugins[format_name]
            ext = plugin_cls.supported_extensions[0]
            out_path_for_plugin = base_name.with_suffix(ext)
            try:
                plugin_inst = plugin_cls(self)
                plugin_inst.generate_output(out_path_for_plugin)
                self.logger.info(f"Generated '{format_name}' output => {out_path_for_plugin}")
            except Exception as e:
                self.logger.error(f"Error generating {format_name} output: {e}")

def discover_plugins(disabled_plugins: Set[str]) -> Dict[str, Type[OutputPlugin]]:
    """
    Discover and load output plugins from the plugins/outputs directory.
    """
    plugins_dict = {}
    plugins_dir = Path(__file__).parent / "plugins" / "outputs"
    if not plugins_dir.exists():
        logger.warning(f"Output plugins directory does not exist at {plugins_dir}")
        return plugins_dict
    project_root = plugins_dir.parent
    import sys
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    for plugin_file in plugins_dir.glob("*.py"):
        if plugin_file.name.startswith("_"):
            continue
        try:
            module_name = f"single_file.plugins.outputs.{plugin_file.stem}"
            plugin_module = importlib.import_module(module_name)
            for name, obj in inspect.getmembers(plugin_module):
                if (inspect.isclass(obj) and issubclass(obj, OutputPlugin) and obj is not OutputPlugin and obj.format_name):
                    if obj.format_name in disabled_plugins:
                        logger.info(f"Plugin '{obj.format_name}' is disabled.")
                        continue
                    plugins_dict[obj.format_name] = obj
                    logger.info(f"Loaded plugin for format: {obj.format_name}")
        except Exception as e:
            logger.error(f"Error loading plugin {plugin_file}: {e}")
    return plugins_dict

# --- Main Function ---
def main(cli_args=None):
    if cli_args is None:
        cli_args = sys.argv[1:]
    
    # If --query or any form of help is requested, disable logging.
    if any(arg in ("--query", "--help", "-h") for arg in cli_args):
        logging.disable(logging.CRITICAL)
    
    # Phase 1: Parse core arguments.
    phase1_parser = argparse.ArgumentParser(add_help=False)
    BaseArguments.add_core_arguments(phase1_parser)
    phase1_parser.add_argument("--config", default=None, help="Path to a JSON config file")
    phase1_parser.add_argument("--disable-plugin", nargs="*", default=[], help="Disable plugins")
    phase1_parser.add_argument("--query", nargs="+", default=None, help="Query available items")
    phase1_args, remaining_args = phase1_parser.parse_known_args(cli_args)
    
    # Merge configuration file if provided.
    if phase1_args.config:
        config_path = Path(phase1_args.config)
        if config_path.is_file():
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            for key, value in config_data.items():
                if hasattr(phase1_args, key):
                    setattr(phase1_args, key, value)
    
    logger.info("Phase 1 arguments:")
    for key, val in vars(phase1_args).items():
        logger.info(f"  {key} => {val}")
    
    disabled_plugin_set = set(phase1_args.disable_plugin)
    active_plugins = discover_plugins(disabled_plugin_set)
    
    # Phase 2: Create final parser (which also adds plugin-specific arguments).
    phase2_parser = argparse.ArgumentParser(parents=[phase1_parser], add_help=False)
    for plugin_class in active_plugins.values():
        plugin_class.add_arguments(phase2_parser)
    phase2_parser.add_argument("-h", "--help", action="help", help="Show help message")
    final_args = phase2_parser.parse_args(cli_args)
    actual_args = BaseArguments.from_namespace(final_args)
    
    # Create the analyzer and assign active output plugins.
    analyzer = CodebaseAnalyzer(actual_args, disabled_plugin_set)
    analyzer.plugins = active_plugins
    for plugin_class in active_plugins.values():
        analyzer.plugins[plugin_class.format_name] = plugin_class

    # If --query is requested, print a summary of available formats, metadata, plugins, and configs.
    if actual_args.query:
        query_summary = {}
        requested_queries = [q.lower() for q in actual_args.query]
        
        # 1. Output formats.
        if "formats" in requested_queries:
            query_summary["formats"] = {
                fmt_name: {
                    "extensions": plugin_class.supported_extensions,
                    "description": getattr(plugin_class, "description", "")
                }
                for fmt_name, plugin_class in active_plugins.items()
            }
        
        # 2. Dynamic metadata configuration.
        if "metadata" in requested_queries:
            query_summary["metadata"] = analyzer.metadata_config
        
        # 3. Metadata and output plugins.
        if "plugins" in requested_queries:
            query_summary["metadata_plugins"] = {
                key: {
                    "default": getattr(plugin, "default", False),
                    "description": getattr(plugin, "description", "")
                }
                for key, plugin in analyzer.metadata_plugins.items()
            }
            query_summary["output_plugins"] = {
                key: {
                    "extensions": getattr(plugin, "supported_extensions", []),
                    "description": getattr(plugin, "description", "")
                }
                for key, plugin in active_plugins.items()
            }
        
        # 4. Configuration files.
        if "configs" in requested_queries:
            config_files = []
            default_configs_dir = Path(__file__).parent.parent / "configs"
            if default_configs_dir.exists():
                for conf_file in default_configs_dir.glob("*.json"):
                    config_files.append({
                        "path": str(conf_file.resolve()),
                        "file": conf_file.name
                    })
            import os
            env_config_paths = os.environ.get("SINGLEFILE_CONFIG_PATH")
            if env_config_paths:
                for config_dir in env_config_paths.split(":"):
                    env_dir = Path(config_dir).resolve()
                    if env_dir.exists() and env_dir.is_dir():
                        for conf_file in env_dir.glob("*.json"):
                            config_files.append({
                                "path": str(conf_file.resolve()),
                                "file": conf_file.name
                            })
            query_summary["configs"] = config_files
        
        print(json.dumps(query_summary, indent=2, default=str))
        return 0

    try:
        analyzer.generate_outputs()
    except Exception as gen_err:
        logger.error(f"Error during execution: {gen_err}")
        traceback.print_exc()
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())


