# single_file_dev01/__main__.py

import sys
import argparse
import traceback
import json
import logging
import importlib
import inspect
from pathlib import Path
from typing import Type, Set, Dict

from single_file.core import OutputPlugin, BaseArguments, FileCollector
from single_file.singlefile import CodebaseAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def discover_plugins(disabled_plugins: Set[str]) -> Dict[str, Type[OutputPlugin]]:
    """
    Discover and load output plugins from the plugins directory, excluding disabled ones.
    """
    plugins = {}
    plugins_dir = Path(__file__).parent / "single_file" / "plugins" / "outputs"

    if not plugins_dir.exists():
        logger.warning(f"Output plugins directory does not exist at {plugins_dir}")
        return plugins

    # Add parent directory to Python path if needed
    project_root = plugins_dir.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Import each Python file in the outputs directory
    for plugin_file in plugins_dir.glob("*.py"):
        if plugin_file.name.startswith("_"):
            continue

        try:
            # Import using absolute import
            module_name = f"single_file.plugins.outputs.{plugin_file.stem}"
            module = importlib.import_module(module_name)

            # Find all OutputPlugin subclasses in the module
            for name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, OutputPlugin)
                    and obj is not OutputPlugin
                    and obj.format_name
                ):
                    if obj.format_name in disabled_plugins:
                        logger.info(
                            f"Plugin '{obj.format_name}' is disabled and will not be loaded."
                        )
                        continue
                    plugins[obj.format_name] = obj
                    logger.info(f"Loaded plugin for format: {obj.format_name}")

        except Exception as e:
            logger.error(f"Error loading plugin {plugin_file}: {e}")

    return plugins


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    # ------------------------------------------------------
    # PHASE-1 PARSER: parse core args and detect --config
    # ------------------------------------------------------
    phase1_parser = argparse.ArgumentParser(
        description="Single File Dev01 CLI - Scans folders and files.",
        add_help=False,  # We'll add help in Phase-2
    )

    # (A) Add the new --config argument:
    phase1_parser.add_argument(
        "--config",
        default=None,
        help="Path to a JSON config file with preset arguments."
    )

    # (B) Add disable-plugin + other base arguments:
    phase1_parser.add_argument(
        "--disable-plugin",
        nargs="*",
        default=[],
        help="Disable one or more plugins by name",
    )
    BaseArguments.add_core_arguments(phase1_parser)

    # Parse just these initial arguments
    try:
        phase1_args, remaining_argv = phase1_parser.parse_known_args(args)
    except Exception as e:
        logger.error(f"Argument parsing failed: {e}")
        sys.exit(1)

    # ------------------------------------------------------
    # MERGE CONFIG (if --config was given) INTO phase1_args
    # ------------------------------------------------------
    if phase1_args.config:
        config_path = Path(phase1_args.config)
        if not config_path.is_file():
            logger.error(f"Config file {config_path} does not exist or is not readable.")
            sys.exit(1)

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load JSON from {config_path}: {e}")
            sys.exit(1)

        # Merge config_data into phase1_args
        for key, value in config_data.items():
            if hasattr(phase1_args, key):
                setattr(phase1_args, key, value)
            else:
                logger.warning(f"Ignoring unrecognized config key: {key}")

    # Just printing out to check what we have after merging:
    logger.info("Arguments after merging config (Phase-1):")
    for arg_name in vars(phase1_args):
        logger.info(f"  {arg_name} => {getattr(phase1_args, arg_name)}")

    # ------------------------------------------------------
    # DISCOVER & LOAD ACTIVE PLUGINS
    # ------------------------------------------------------
    disabled_plugins = set(phase1_args.disable_plugin)
    active_plugins = discover_plugins(disabled_plugins)

    # ------------------------------------------------------
    # PHASE-2 PARSER: plugin arguments & final parse
    # ------------------------------------------------------
    phase2_parser = argparse.ArgumentParser(
        description="Single File Dev01 CLI - Scans folders and files.",
        parents=[phase1_parser],
        add_help=False,
    )

    # IMPORTANT: Use config-based values as defaults unless overridden on CLI
    phase2_parser.set_defaults(**vars(phase1_args))

    # Let active plugins add their CLI arguments
    for plugin_cls in active_plugins.values():
        plugin_cls.add_arguments(phase2_parser)

    phase2_parser.add_argument(
        "-h", "--help", action="help", help="Show this help message and exit"
    )

    # Now we do the final parse
    try:
        final_args = phase2_parser.parse_args(args)
    except Exception as e:
        logger.error(f"Argument parsing failed: {e}")
        sys.exit(1)

    # Convert to BaseArguments
    actual_args = BaseArguments.from_namespace(final_args)

    # Initialize CodebaseAnalyzer
    analyzer = CodebaseAnalyzer(actual_args, disabled_plugins)
    analyzer.plugins = active_plugins

    # Map file extensions to plugin classes
    for plugin_cls in active_plugins.values():
        for ext in plugin_cls.supported_extensions:
            ext_lower = ext.lower()
            if not ext_lower.startswith('.'):
                ext_lower = '.' + ext_lower
            analyzer.extension_plugin_map.setdefault(ext_lower, []).append(plugin_cls)

    # Show which plugins are active
    logger.info("Active Plugins:")
    for plugin_name in analyzer.plugins.keys():
        logger.info(f"  - {plugin_name}")

    # Actually run the analyzer
    try:
        analyzer.generate_outputs()
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        traceback.print_exc()
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
