import unittest
import subprocess
import sys
import os
import shutil
import tempfile
from pathlib import Path
from itertools import product
from datetime import datetime

class TestComprehensiveE2E(unittest.TestCase):
    """
    A comprehensive E2E test that:
      1) Creates a controlled, multi-level directory structure with various files.
      2) Iterates through many combinations of CLI options.
      3) Calls 'single-file' CLI for each combination, capturing pass/fail.
      4) Writes a detailed report to a persistent folder so it won't be deleted.
    """

    @classmethod
    def setUpClass(cls):
        """
        1) Create a temporary directory to hold test data files.
        2) Create a persistent directory for logs (so it won't be deleted).
        3) Create test data (subdirs/files).
        """
        # Keep track of all pass/fail in a class-level list.
        cls.test_results = []

        # 1) Create ephemeral test-data sandbox.
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="singlefile_e2e_"))

        # 2) Create or use a persistent 'test_logs' directory next to this script:
        script_dir = Path(__file__).parent.resolve()
        cls.log_dir = script_dir / "test_e2e_logs"
        cls.log_dir.mkdir(exist_ok=True)
        cls.report_file = f"./test_e2e_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        # cls.report_file = cls.log_dir / f"test_e2e_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        # 3) Create some subdirectories for test data:
        (cls.temp_dir / "dir_a").mkdir()
        (cls.temp_dir / "dir_b").mkdir()
        (cls.temp_dir / "dir_b" / "sub_b1").mkdir()
        (cls.temp_dir / "node_modules").mkdir()  # might be excluded

        # Create files of various types in different paths:
        (cls.temp_dir / "dir_a" / "file_a.py").write_text("# file_a.py\nprint('Hello from A')\n", encoding="utf-8")
        (cls.temp_dir / "dir_a" / "config.json").write_text('{"name":"config"}\n', encoding="utf-8")
        (cls.temp_dir / "dir_b" / "README.md").write_text("# README in dir_b\nSome *markdown* text.\n", encoding="utf-8")
        (cls.temp_dir / "dir_b" / "sub_b1" / "script_b1.py").write_text("print('Inside sub_b1')\n", encoding="utf-8")
        (cls.temp_dir / "image.bin").write_bytes(b"\x00\x01\x02\x03\xFF\xFEThisIsBinaryData")
        (cls.temp_dir / "exclude_me.log").write_text("This is a .log file that may be excluded", encoding="utf-8")
        (cls.temp_dir / "node_modules" / "nm_stuff.py").write_text("print('Inside node_modules')\n", encoding="utf-8")
        (cls.temp_dir / "notes").write_text("Just a text file with no extension.\n", encoding="utf-8")

        print(f"\n[SetupClass] Created ephemeral test sandbox in: {cls.temp_dir}")
        print(f"[SetupClass] Test logs will go into: {cls.log_dir}")

    @classmethod
    def tearDownClass(cls):
        """
        Clean up after tests. If you want to keep ephemeral sandbox for inspection,
        comment out or remove the rmtree. By default, we'll keep it to debug Return code: 2 issues.
        """
        # If you'd like to remove it:
        # shutil.rmtree(cls.temp_dir, ignore_errors=True)
        # print(f"[TearDownClass] Removed ephemeral test sandbox: {cls.temp_dir}")

        print(f"[TearDownClass] **NOT** removing ephemeral sandbox for debugging: {cls.temp_dir}")
        print(f"[TearDownClass] Logs in: {cls.log_dir}\n")

    def run_single_file_cli(self, extra_args, label=""):
        """
        Helper to run the single-file CLI with given arguments, analyzing the ephemeral sandbox.
        Return (return_code, stdout, stderr, final_cmd).
        """
        # If your code is installed in the environment, you can do:
        # cmd = ["single-file"] + ...
        # or if you're using 'python -m single_file.singlefile', ensure PYTHONPATH is set or you did `pip install -e .`.
        cmd = [
            sys.executable,
            "-m", "single_file.singlefile",
            "--paths", str(self.temp_dir),
        ] + extra_args

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()

        return process.returncode, stdout, stderr, cmd

    def _test_with_options(self, options):
        """
        Perform one test run with a given set of CLI options (dict).
        Return a dict summarizing pass/fail info.
        """
        args = []

        # Convert 'options' dict into CLI flags
        if "depth" in options:
            args += ["--depth", str(options["depth"])]
        if options.get("ignore_errors", False):
            args += ["--ignore-errors"]
        if options.get("replace_invalid_chars", False):
            args += ["--replace-invalid-chars"]
        # if options.get("absolute_paths", False):
        #     args += ["--absolute-paths"]
        if "extensions" in options and options["extensions"]:
            args += ["--extensions"] + options["extensions"]
        if "exclude_extensions" in options and options["exclude_extensions"]:
            args += ["--exclude-extensions"] + options["exclude_extensions"]
        if "exclude_dirs" in options and options["exclude_dirs"]:
            args += ["--exclude-dirs"] + options["exclude_dirs"]
        if "exclude_files" in options and options["exclude_files"]:
            args += ["--exclude-files"] + options["exclude_files"]
        if "include_dirs" in options and options["include_dirs"]:
            args += ["--include-dirs"] + options["include_dirs"]
        if "include_files" in options and options["include_files"]:
            args += ["--include-files"] + options["include_files"]
        if "metadata_add" in options and options["metadata_add"]:
            args += ["--metadata-add"] + options["metadata_add"]
        if "metadata_remove" in options and options["metadata_remove"]:
            args += ["--metadata-remove"] + options["metadata_remove"]
        if options.get("force_binary_content", False):
            args += ["--force-binary-content"]

        # Decide how to name the output file:
        # We generate separate files so each run doesn't overwrite another's output.
        if "formats" in options and options["formats"]:
            out_file = self.temp_dir / "test_output" / f"output_{options['test_name']}"
            args += ["--formats", ",".join(options["formats"]), "--output-file", str(out_file)]
        else:
            # fallback if none specified
            out_file = self.temp_dir / "test_output" / f"output_{options['test_name']}.txt"
            args += ["--output-file", str(out_file)]

        # Run it
        rc, stdout, stderr, final_cmd = self.run_single_file_cli(args, label=options["test_name"])

        return {
            "label": options["test_name"],
            "cmd": " ".join(map(str, final_cmd)),
            "returncode": rc,
            "stdout_snippet": stdout[:200] + ("..." if len(stdout) > 200 else ""),
            "stderr_snippet": stderr[:200] + ("..." if len(stderr) > 200 else ""),
            "passed": (rc == 0),
        }

    def test_all_combinations(self):
        """
        Main test that enumerates multiple combinations of CLI options, runs them,
        and writes a final report to a persistent file.
        """
        # Define the dimension values for each CLI option:
        depths = [0, 1, 2]
        ignore_errors_opts = [False, True]
        replace_invalid_chars_opts = [False, True]
        absolute_paths_opts = [False, True]
        extensions_opts = [[], ["py", "json"], ["md"]]
        exclude_extensions_opts = [[], ["log", "bin"]]
        exclude_dirs_opts = [[], ["^node_modules$"]]
        exclude_files_opts = [[], [r".*\.log$"]]
        include_dirs_opts = [[], ["^dir_a$"]]
        include_files_opts = [[], [r".*\.py$"]]
        format_combos = [
            ["default"],
            ["json"],
            ["default", "json"],
        ]

        # Build all combos with itertools.product
        all_combinations = []
        test_count = 0

        for (depth,
             ign_err,
             repl_inv,
             abs_paths,
             exts,
             excl_exts,
             excl_dirs,
             excl_files,
             inc_dirs,
             inc_files,
             fmts
        ) in product(depths,
                     ignore_errors_opts,
                     replace_invalid_chars_opts,
                     absolute_paths_opts,
                     extensions_opts,
                     exclude_extensions_opts,
                     exclude_dirs_opts,
                     exclude_files_opts,
                     include_dirs_opts,
                     include_files_opts,
                     format_combos):
            test_count += 1
            test_name = f"test_{test_count}"
            combo = {
                "test_name": test_name,
                "depth": depth,
                "ignore_errors": ign_err,
                "replace_invalid_chars": repl_inv,
                "absolute_paths": abs_paths,
                "extensions": exts,
                "exclude_extensions": excl_exts,
                "exclude_dirs": excl_dirs,
                "exclude_files": excl_files,
                "include_dirs": inc_dirs,
                "include_files": inc_files,
                "formats": fmts
            }
            all_combinations.append(combo)

        print(f"[INFO] Attempting {len(all_combinations)} combinations...")

        # Run them
        for combo in all_combinations:
            result = self._test_with_options(combo)
            self.__class__.test_results.append(result)

        # Summaries
        fails = [r for r in self.test_results if not r["passed"]]
        passes = [r for r in self.test_results if r["passed"]]

        print("\n================== Test Summary ==================")
        print(f"Total combinations tested: {len(self.test_results)}")
        print(f"Failures: {len(fails)}")

        # Write final test report to a persistent file
        self.write_report_file(fails, passes)

        # Optionally fail if any combos fail:
        if fails:
            # Print some details for debugging
            print("\n---- FAIL DETAILS ----")
            for f in fails:
                print(f"Test label: {f['label']}")
                print(f"Cmd: {f['cmd']}")
                print(f"Return code: {f['returncode']}")
                print(f"Stderr snippet: {f['stderr_snippet']}")
                print("----------------------------------\n")

        self.assertEqual(len(fails), 0, f"Some SingleFile combos failed => {len(fails)} failed.")

    def write_report_file(self, fails, passes):
        """
        Writes a persistent test report so we can see pass/fail details even after the test ends.
        """
        lines = []
        lines.append("=== SingleFile E2E Test Report ===")
        lines.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Ephemeral test sandbox: {self.temp_dir}")
        lines.append("")
        lines.append("SUMMARY:")
        lines.append(f"  Total combos: {len(self.test_results)}")
        lines.append(f"  Passes: {len(passes)}")
        lines.append(f"  Fails: {len(fails)}")
        lines.append("")
        if fails:
            lines.append("FAIL DETAILS:")
            for f_ in fails:
                lines.append(f"Label: {f_['label']}")
                lines.append(f"Cmd: {f_['cmd']}")
                lines.append(f"Return Code: {f_['returncode']}")
                lines.append(f"Stderr snippet: {f_['stderr_snippet']}")
                lines.append("-" * 40)
            lines.append("")
        lines.append("PASS DETAILS:")
        for p_ in passes:
            lines.append(f"Label: {p_['label']}")
            lines.append(f"Cmd: {p_['cmd']}")
            lines.append("-" * 40)

        with open(self.report_file, "w", encoding="utf-8") as rf:
            rf.write("\n".join(lines))

        print(f"[INFO] Full test report written to: {self.report_file}")

if __name__ == "__main__":
    unittest.main(argv=[""], verbosity=2, exit=True)
