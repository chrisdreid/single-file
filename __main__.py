#!/usr/bin/env python
"""
Main entry point for SingleFile.
This file parses command-line arguments, loads configuration, discovers plugins,
and either performs a query or runs the analyzer.
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

from single_file.core import OutputPlugin, BaseArguments
from single_file.singlefile import CodebaseAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def discover_plugins(disabled_plugins: Set[str]) -> Dict[str, Type[OutputPlugin]]:
    """
    Discover and load output plugins from the plugins directory, excluding those disabled.
    """
    plugins_dict = {}
    plugins_dir = Path(__file__).parent / "single_file" / "plugins" / "outputs"

    if not plugins_dir.exists():
        logger.warning(f"Output plugins directory does not exist at {plugins_dir}")
        return plugins_dict

    # Ensure the project root is in sys.path for absolute imports
    project_root = plugins_dir.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Import each Python file in the outputs directory
    for plugin_file in plugins_dir.glob("*.py"):
        if plugin_file.name.startswith("_"):
            continue
        try:
            module_name = f"single_file.plugins.outputs.{plugin_file.stem}"
            plugin_module = importlib.import_module(module_name)
            # Find all subclasses of OutputPlugin in the module
            for member_name, member_obj in inspect.getmembers(plugin_module):
                if (
                    inspect.isclass(member_obj)
                    and issubclass(member_obj, OutputPlugin)
                    and member_obj is not OutputPlugin
                    and member_obj.format_name
                ):
                    if member_obj.format_name in disabled_plugins:
                        logger.info(
                            f"Plugin '{member_obj.format_name}' is disabled and will not be loaded."
                        )
                        continue
                    plugins_dict[member_obj.format_name] = member_obj
                    logger.info(f"Loaded plugin for format: {member_obj.format_name}")
        except Exception as import_err:
            logger.error(f"Error loading plugin {plugin_file}: {import_err}")

    return plugins_dict


def main(cli_args=None):
    if cli_args is None:
        cli_args = sys.argv[1:]

    # --- SUPPRESS LOGGING IF QUERY IS REQUESTED ---
    if any(arg.startswith("--query") for arg in cli_args):
        logging.disable(logging.CRITICAL)

    # ----------------------------
    # PHASE 1: Initial Argument Parsing
    # ----------------------------
    phase1_parser = argparse.ArgumentParser(
        description="SingleFile CLI - Scans folders and files.",
        add_help=False,
    )
    phase1_parser.add_argument(
        "--config",
        default=None,
        help="Path to a JSON config file with preset arguments."
    )
    phase1_parser.add_argument(
        "--disable-plugin",
        nargs="*",
        default=[],
        help="Disable one or more plugins by name"
    )
    phase1_parser.add_argument(
        "--query",
        nargs="+",
        default=None,
        help="Query available items. Allowed values: formats, metadata, configs. E.g.: --query formats metadata"
    )
    BaseArguments.add_core_arguments(phase1_parser)

    try:
        phase1_args, remaining_args = phase1_parser.parse_known_args(cli_args)
    except Exception as parse_err:
        logger.error(f"Argument parsing failed: {parse_err}")
        sys.exit(1)

    # ----------------------------
    # Merge configuration file if provided
    # ----------------------------
    if phase1_args.config:
        config_path = Path(phase1_args.config)
        if not config_path.is_file():
            logger.error(f"Config file {config_path} does not exist or is not readable.")
            sys.exit(1)
        try:
            with open(config_path, "r", encoding="utf-8") as config_handle:
                config_data = json.load(config_handle)
        except Exception as config_err:
            logger.error(f"Failed to load JSON from {config_path}: {config_err}")
            sys.exit(1)

        for key, value in config_data.items():
            if hasattr(phase1_args, key):
                setattr(phase1_args, key, value)
            else:
                logger.warning(f"Ignoring unrecognized config key: {key}")

    logger.info("Arguments after merging config (Phase 1):")
    for arg_key in vars(phase1_args):
        logger.info(f"  {arg_key} => {getattr(phase1_args, arg_key)}")

    # ----------------------------
    # Discover active plugins
    # ----------------------------
    disabled_plugin_set = set(phase1_args.disable_plugin)
    active_plugins = discover_plugins(disabled_plugin_set)

    # ----------------------------
    # PHASE 2: Final Argument Parsing
    # ----------------------------
    phase2_parser = argparse.ArgumentParser(
        description="SingleFile CLI - Scans folders and files.",
        parents=[phase1_parser],
        add_help=False,
    )
    phase2_parser.set_defaults(**vars(phase1_args))
    for plugin_class in active_plugins.values():
        plugin_class.add_arguments(phase2_parser)
    phase2_parser.add_argument("-h", "--help", action="help", help="Show this help message and exit")

    try:
        final_args = phase2_parser.parse_args(cli_args)
    except Exception as final_err:
        logger.error(f"Final argument parsing failed: {final_err}")
        sys.exit(1)

    actual_args = BaseArguments.from_namespace(final_args)

    # ----------------------------
    # Initialize the analyzer
    # ----------------------------
    analyzer = CodebaseAnalyzer(actual_args, disabled_plugin_set)
    analyzer.plugins = active_plugins

    # Map file extensions to plugin classes
    for plugin_class in active_plugins.values():
        for ext in plugin_class.supported_extensions:
            ext_lower = ext.lower() if ext.startswith(".") else "." + ext.lower()
            analyzer.extension_plugin_map.setdefault(ext_lower, []).append(plugin_class)

    logger.info("Active Plugins:")
    for plugin_name in analyzer.plugins.keys():
        logger.info(f"  - {plugin_name}")

    # ----------------------------
    # Query Mode: Print JSON summary and return if requested
    # ----------------------------
    if actual_args.query:
        query_summary = {}
        requested_queries = [q_item.lower() for q_item in actual_args.query]

        if "formats" in requested_queries:
            query_summary["formats"] = {
                fmt_name: {
                    "extensions": plugin_class.supported_extensions,
                    "description": getattr(plugin_class, "description", "")
                }
                for fmt_name, plugin_class in active_plugins.items()
            }
        if "metadata" in requested_queries:
            query_summary["metadata"] = list(analyzer.metadata_plugins.keys())
        if "configs" in requested_queries:
            config_files = []
            # Always search the default config directory (single-file/configs)
            default_configs_dir = Path(__file__).parent / "single_file" / "configs"
            if default_configs_dir.exists():
                for conf_file in default_configs_dir.glob("*.json"):
                    config_files.append({
                        "path": str(conf_file.resolve()),
                        "file": conf_file.name
                    })
            # Additionally, search directories specified by SINGLEFILE_CONFIG_PATH
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

    # ----------------------------
    # Run the analyzer to generate outputs
    # ----------------------------
    try:
        analyzer.generate_outputs()
    except Exception as gen_err:
        logger.error(f"Error during execution: {gen_err}")
        traceback.print_exc()
        sys.exit(1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
