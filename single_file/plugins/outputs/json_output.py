import json
from datetime import datetime
from pathlib import Path
from single_file.core import OutputPlugin

class JSONOutputPlugin(OutputPlugin):
    """
    Generates a JSON representation of the codebase.
    All file metadata now uses 'filepath' (relative) instead of 'path'.
    The output does not include an explicit 'is_binary' flag.
    """
    format_name = "json"
    supported_extensions = [".json"]
    description = "Generates a JSON representation of the codebase."

    @classmethod
    def add_arguments(cls, parser):
        group = parser.add_argument_group("JSON output options")
        group.add_argument("--json-no-content", action="store_true", help="Exclude file contents")
        group.add_argument("--json-compact", action="store_true", help="Minified JSON output")
        group.add_argument("--json-metadata", nargs="+", metavar="KEY=VALUE", help="Add custom metadata")

    def generate_output(self, output_path: Path) -> None:
        data = {
            "metadata": self._build_metadata(),
            "stats": self.analyzer.stats,
            "file_tree": self.analyzer.file_tree,
            "files": {str(k): v for k, v in self.analyzer.file_info_cache.items()}
        }
        indent = None if getattr(self.args, "json_compact", False) else 2
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, default=str)
        self.analyzer.logger.info(f"JSON output generated at {output_path}")

    def _build_metadata(self) -> dict:
        meta = {
            "generated_at": datetime.now().isoformat(),
            "tool_version": "1.0.0",
            "command_args": vars(self.args)
        }
        return meta
