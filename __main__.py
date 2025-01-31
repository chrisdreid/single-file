# __main__.py

import sys
import argparse
import traceback

def main(args):
    if args is None:
        args = sys.argv[1:]

    # Phase 1 parser: minimal arguments
    phase1_parser = argparse.ArgumentParser(
        description="Single File Dev01 CLI",
        add_help=False
    )
    phase1_parser.add_argument('--help', action='help', help='Show this help and exit')
    phase1_parser.add_argument('--disable-plugin', nargs='*', default=[],
                               help='Disable one or more plugins by name')

    # Example core arguments
    phase1_parser.add_argument('--paths', nargs='*', default=['.'])
    phase1_parser.add_argument('--output-dir', default='output')
    phase1_parser.add_argument('--formats', default='default')
    phase1_parser.add_argument('--skip-errors', action='store_true')

    phase1_args, remaining_argv = phase1_parser.parse_known_args(args)
    disabled_plugins = set(phase1_args.disable_plugin)

    from single_file.singlefile import CodebaseAnalyzer
    from single_file.core import BaseArguments

    # Create "dummy" args for loading plugins
    dummy_args = BaseArguments()
    dummy_args.paths = phase1_args.paths
    dummy_args.output_dir = phase1_args.output_dir
    dummy_args.formats = phase1_args.formats
    dummy_args.skip_errors = phase1_args.skip_errors

    # Load plugins (and skip disabled ones)
    analyzer = CodebaseAnalyzer(dummy_args)
    for plugin_name in list(analyzer.plugins.keys()):
        if plugin_name in disabled_plugins:
            del analyzer.plugins[plugin_name]

    # Now let the active plugins add additional arguments
    for plugin_cls in analyzer.plugins.values():
        plugin_cls.add_arguments(phase1_parser)

    # Re-enable or add normal help
    phase1_parser.add_argument('--help', action='help', help='Show help and exit')

    # Parse again fully
    final_args = phase1_parser.parse_args(remaining_argv)
    actual_args = BaseArguments.from_namespace(final_args)

    # Re-create analyzer with final arguments
    analyzer = CodebaseAnalyzer(actual_args)

    try:
        # For debugging
        print("=== Final Arguments ===")
        for k, v in vars(final_args).items():
            print(f"{k}: {v}")

        # Run analysis
        analyzer.generate_outputs()

    except Exception as e:
        print(f"Error during execution: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    args = sys.argv[1:]
    main(args)
