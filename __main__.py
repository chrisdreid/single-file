# single_file_dev01/__main__.py

import sys
import argparse
import traceback
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

    Args:
        disabled_plugins: Set of plugin names to disable

    Returns:
        Dict mapping format_name to OutputPlugin class
    """
    plugins = {}
    plugins_dir = Path(__file__).parent / "single_file" / "plugins"

    if not plugins_dir.exists():
        logger.warning(f"Plugins directory does not exist at {plugins_dir}")
        return plugins

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

    # Phase 1 parser: parse core arguments and disabled plugins
    phase1_parser = argparse.ArgumentParser(
        description="Single File Dev01 CLI - Scans folders and files.",
        add_help=False,  # We'll add help manually to prevent duplication
    )
    phase1_parser.add_argument(
        "-h", "--help", action="help", help="Show this help message and exit"
    )
    phase1_parser.add_argument(
        "--disable-plugin",
        nargs="*",
        default=[],
        help="Disable one or more plugins by name",
    )

    # Add core arguments with standardized names
    BaseArguments.add_core_arguments(phase1_parser)

    # Parse initial arguments
    try:
        phase1_args, remaining_argv = phase1_parser.parse_known_args(args)
    except Exception as e:
        logger.error(f"Argument parsing failed: {e}")
        sys.exit(1)

    disabled_plugins = set(phase1_args.disable_plugin)

    # Print default arguments
    logger.info("Default Script Arguments:")
    for arg in vars(phase1_args):
        logger.info(f"  {arg}: {getattr(phase1_args, arg)}")

    # Discover and load active plugins excluding disabled_plugins
    active_plugins = discover_plugins(disabled_plugins)

    # Create a new parser including plugin-specific arguments
    phase2_parser = argparse.ArgumentParser(
        description="Single File Dev01 CLI - Scans folders and files.",
        parents=[phase1_parser],
        add_help=False,  # Prevent argparse from adding help again
    )

    # Let active plugins add their arguments
    for plugin_cls in active_plugins.values():
        plugin_cls.add_arguments(phase2_parser)

    # Re-add help to include plugin arguments
    # phase2_parser.add_argument(
    #     "-h", "--help", action="help", help="Show this help message and exit"
    # )

    # Parse all arguments with the full parser
    try:
        final_args = phase2_parser.parse_args(args)
    except Exception as e:
        logger.error(f"Argument parsing failed: {e}")
        sys.exit(1)

    # Convert to BaseArguments
    actual_args = BaseArguments.from_namespace(final_args)

    # Initialize CodebaseAnalyzer once with all arguments and disabled plugins
    analyzer = CodebaseAnalyzer(actual_args, disabled_plugins)

    # Assign active_plugins to analyzer
    analyzer.plugins = active_plugins

    # Display active plugins
    logger.info("Active Plugins:")
    for plugin_name in analyzer.plugins.keys():
        logger.info(f"  - {plugin_name}")

    try:
        # For debugging purposes
        logger.debug("=== Final Arguments ===")
        for k, v in vars(final_args).items():
            logger.debug(f"{k}: {v}")

        # Run analysis
        analyzer.generate_outputs()

    except Exception as e:
        logger.error(f"Error during execution: {e}")
        traceback.print_exc()
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
