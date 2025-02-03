import unittest
import subprocess
import sys
import os
import shutil
import tempfile
import json
from pathlib import Path
from itertools import product
from datetime import datetime

class TestComprehensiveE2E(unittest.TestCase):
    """
    A comprehensive E2E test for SingleFile that:
      1) Creates an ephemeral test sandbox with known files/subdirs.
      2) Tests multiple CLI option combinations (including optional config files).
      3) Validates:
         - Return code is 0 (means no crash).
         - For JSON outputs: parse & confirm the correct structure, files, etc.
         - For Markdown outputs: check that certain content is present/absent.
      4) Writes a final report to a persistent folder for inspection.
    """

    @classmethod
    def setUpClass(cls):
        """
        1) Creates ephemeral test sandbox
        2) Creates persistent logs folder
        3) Creates known test data and sample config files
        """
        cls.test_results = []

        # 1) Ephemeral test sandbox in /tmp
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="singlefile_e2e_"))

        # 2) Persistent logs directory
        script_dir = Path(__file__).parent.resolve()
        cls.log_dir = script_dir / "test_e2e_logs"
        cls.log_dir.mkdir(exist_ok=True)
        cls.report_file = cls.log_dir / f"test_e2e_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        # 3) Build subdirs, files (known content so we can validate them)
        (cls.temp_dir / "dir_a").mkdir()
        (cls.temp_dir / "dir_b").mkdir()
        (cls.temp_dir / "dir_b" / "sub_b1").mkdir()
        (cls.temp_dir / "node_modules").mkdir()  # might be excluded

        # Known contents to check for in outputs
        cls.file_a_py_content = "# file_a.py\nprint('Hello from A')\n"
        cls.config_json_content = '{"name":"config"}\n'
        cls.readme_md_content = "# README in dir_b\nSome *markdown* text.\n"
        cls.script_b1_py_content = "print('Inside sub_b1')\n"
        cls.image_bin_data = b"\x00\x01\x02\x03\xFF\xFEThisIsBinaryData"
        cls.log_file_content = "This is a .log file that may be excluded"
        cls.nm_stuff_py_content = "print('Inside node_modules')\n"
        cls.notes_content = "Just a text file with no extension.\n"

        (cls.temp_dir / "dir_a" / "file_a.py").write_text(cls.file_a_py_content, encoding="utf-8")
        (cls.temp_dir / "dir_a" / "config.json").write_text(cls.config_json_content, encoding="utf-8")
        (cls.temp_dir / "dir_b" / "README.md").write_text(cls.readme_md_content, encoding="utf-8")
        (cls.temp_dir / "dir_b" / "sub_b1" / "script_b1.py").write_text(cls.script_b1_py_content, encoding="utf-8")
        (cls.temp_dir / "image.bin").write_bytes(cls.image_bin_data)
        (cls.temp_dir / "exclude_me.log").write_text(cls.log_file_content, encoding="utf-8")
        (cls.temp_dir / "node_modules" / "nm_stuff.py").write_text(cls.nm_stuff_py_content, encoding="utf-8")
        (cls.temp_dir / "notes").write_text(cls.notes_content, encoding="utf-8")

        # Also create some *sample config files* in the sandbox (or store them in your project if you prefer)
        cls.sample_config_1 = cls.temp_dir / "sample_config_1.json"
        cls.sample_config_1.write_text(
            json.dumps({
                "exclude_dirs": ["^node_modules$"],
                "extensions": ["py", "json"],
                "exclude_extensions": ["log"]
            }, indent=2),
            encoding="utf-8"
        )

        cls.sample_config_2 = cls.temp_dir / "sample_config_2.json"
        cls.sample_config_2.write_text(
            json.dumps({
                "metadata_add": ["md5", "filesize_human_readable"],
                "formats": "json",
                "ignore_errors": True
            }, indent=2),
            encoding="utf-8"
        )

        print(f"\n[SetupClass] Created ephemeral test sandbox in: {cls.temp_dir}")
        print(f"[SetupClass] Test logs => {cls.report_file}")

    @classmethod
    def tearDownClass(cls):
        """
        By default, keep ephemeral sandbox around for inspection.
        """
        # If you prefer to remove it, uncomment:
        # shutil.rmtree(cls.temp_dir, ignore_errors=True)
        print(f"[TearDownClass] **NOT** removing ephemeral sandbox => {cls.temp_dir}\n"
              f"[TearDownClass] Logs => {cls.report_file}\n")

    def run_single_file_cli(self, extra_args, label=""):
        """
        Launches SingleFile with a set of arguments. Returns:
          (returncode, stdout, stderr, final_cmd)
        """
        # If your SingleFile is installed, you could do ["single-file"] + extra_args.
        # If using python -m single_file.singlefile, ensure environment is correct (pip install -e . or PYTHONPATH).
        cmd = [
            sys.executable,
            "-m", "single_file.singlefile",
            "--paths", str(self.temp_dir),
        ] + extra_args

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        return process.returncode, stdout, stderr, cmd

    def _verify_json_output(self, json_path, options):
        """
        Parse the generated JSON file. Verify top-level structure (tool_metadata, stats, file_tree, files).
        Then optionally confirm that included or excluded files match expectation based on 'options'.
        Return (bool_ok, message).
        """
        if not json_path.exists():
            return False, f"JSON output file not found at {json_path}"

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as e:
            return False, f"Failed to parse JSON: {e}"

        # Basic structure checks
        required_keys = ["tool_metadata", "stats", "file_tree", "files"]
        for rk in required_keys:
            if rk not in data:
                return False, f"Missing '{rk}' in JSON output"

        files_list = data["files"]
        if not isinstance(files_list, list):
            return False, f"Expected 'files' to be a list; got {type(files_list)}"

        # Example: If "extensions": ["py","json"], we only expect those in 'files' 
        # or if "exclude_extensions": ["log"], ensure no ".log" is present, etc.
        # We'll do a minimal demonstration.
        allowed_exts = options.get("extensions")
        exclude_exts = options.get("exclude_extensions", [])

        for fobj in files_list:
            ext = fobj.get("extension", "")
            filepath = fobj.get("filepath", "")
            # If we have a known exclude ext
            if ext in exclude_exts:
                return False, f"Found excluded extension '{ext}' in file {filepath}"
            # If we have a known allow list
            if allowed_exts and ext not in allowed_exts and ext != "":
                # e.g. user said only py/json, but we found md => fail
                return False, f"Found unexpected extension '{ext}' in file {filepath}"

        # Additional checks can go here if you want to ensure line_count is correct, etc.
        return True, "JSON output structure and file list checks passed."

    def _verify_markdown_output(self, md_path):
        """
        Search for known file contents in the Markdown output.
        Return (bool_ok, message).
        """
        if not md_path.exists():
            return False, f"Markdown output file not found at {md_path}"

        text = md_path.read_text(encoding="utf-8")

        # Check that certain known lines appear
        # e.g. we expect file_a.py's content "print('Hello from A')" to appear
        if "# file_a.py" not in text or "Hello from A" not in text:
            return False, "Missing content from file_a.py in Markdown"
        if "# README in dir_b" not in text:
            return False, "Missing content from README.md"

        # Possibly check that excluded logs didn't appear
        if "This is a .log file that may be excluded" in text:
            return False, "Log file content unexpectedly found in Markdown"

        return True, "Markdown content checks passed."

    def _test_with_options(self, options):
        """
        1) Construct command-line args from `options`.
        2) Run SingleFile.
        3) If successful (rc=0), do deeper output checks for JSON or Markdown.
        """
        args = []

        # Possibly use a config file
        if options.get("config_file"):
            args += ["--config", str(options["config_file"])]

        # Standard SingleFile arguments
        if "depth" in options:
            args += ["--depth", str(options["depth"])]
        if options.get("ignore_errors", False):
            args += ["--ignore-errors"]
        if options.get("replace_invalid_chars", False):
            args += ["--replace-invalid-chars"]
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

        # Decide the output file naming
        fmts = options.get("formats", [])
        if not fmts:
            # fallback
            fmts = ["default"]
        # We assume the test code sets the output_file = test_output/<combo> 
        # SingleFile might produce multiple files if multiple formats are specified, 
        # but let's assume SingleFile only uses the extension from the plugin to determine final name if no suffix is given
        out_base = self.temp_dir / "test_output"
        out_base.mkdir(exist_ok=True)
        out_file = out_base / f"output_{options['test_name']}"

        args += ["--formats", ",".join(fmts)]
        args += ["--output-file", str(out_file)]

        rc, stdout, stderr, final_cmd = self.run_single_file_cli(args, label=options["test_name"])

        # Build the result record
        result = {
            "label": options["test_name"],
            "cmd": " ".join(map(str, final_cmd)),
            "returncode": rc,
            "stdout_snippet": stdout[:200] + ("..." if len(stdout) > 200 else ""),
            "stderr_snippet": stderr[:200] + ("..." if len(stderr) > 200 else ""),
            "passed": (rc == 0),
            "output_checks": []
        }

        # If the command passed, do deeper checks
        if rc == 0:
            # For each format, we do separate validation
            for f_ in fmts:
                if f_ == "json":
                    # By default, SingleFile's JSON plugin might produce .json
                    # If SingleFile does the typical approach, the final path might be 'output_<test>.[.json]'
                    json_path = out_file.with_suffix(".json")
                    ok_json, msg_json = self._verify_json_output(json_path, options)
                    if not ok_json:
                        result["passed"] = False
                        result["output_checks"].append(msg_json)
                    else:
                        result["output_checks"].append(msg_json)
                elif f_ == "markdown":
                    # Usually .md extension
                    md_path = out_file.with_suffix(".md")
                    ok_md, msg_md = self._verify_markdown_output(md_path)
                    if not ok_md:
                        result["passed"] = False
                        result["output_checks"].append(msg_md)
                    else:
                        result["output_checks"].append(msg_md)
                elif f_ == "default":
                    # The default might produce .txt or something else
                    txt_path = out_file.with_suffix(".txt")
                    # If you want to do minimal check on the text:
                    if txt_path.exists():
                        txt_content = txt_path.read_text(encoding="utf-8")
                        if "### Directory Structure ###" not in txt_content:
                            result["passed"] = False
                            result["output_checks"].append("Missing 'Directory Structure' marker in default output")
                        else:
                            result["output_checks"].append("Default output text basic check OK")
                    else:
                        # No file found
                        result["passed"] = False
                        result["output_checks"].append("Default output .txt file not found")

                # You can expand for other formats if needed.

        return result

    def test_all_combinations(self):
        """
        Main test enumerating multiple combos of CLI options, including config files,
        then writes final summary report.
        """
        # For demonstration, we pick a smaller set than the full Cartesian product. 
        # You can expand or refine as needed.
        depths = [0, 1]
        ignore_errors_opts = [False, True]
        # We'll skip absolute_paths or other unimplemented flags to avoid usage errors
        # We'll show config_file usage in a separate dimension
        config_files_opts = [
            None,
            self.sample_config_1,  # exclude node_modules, only py/json, exclude log
            self.sample_config_2,  # md5 + file size, JSON only, ignore_errors
        ]

        # We'll try a few formats combos
        format_combos = [
            ["default"],
            ["json"],
            ["markdown"],
            ["default", "json"],
        ]

        # We'll skip enumerating all the exclude/include combos for brevity.
        # Just show a couple:
        exclude_dirs_opts = [
            [],
            ["^node_modules$"]
        ]
        extensions_opts = [
            [],
            ["py"], 
            ["py", "json"]
        ]

        all_combinations = []
        test_count = 0

        for depth, ign_err, config_file, fmts, ex_dirs, exts in product(
                depths, ignore_errors_opts, config_files_opts,
                format_combos, exclude_dirs_opts, extensions_opts
        ):
            test_count += 1
            test_name = f"test_{test_count}"
            combo = {
                "test_name": test_name,
                "depth": depth,
                "ignore_errors": ign_err,
                "config_file": config_file,
                "formats": fmts,
                "exclude_dirs": ex_dirs,
                "extensions": exts,
            }
            all_combinations.append(combo)

        print(f"[INFO] Attempting {len(all_combinations)} combinations...")

        for combo in all_combinations:
            result = self._test_with_options(combo)
            self.__class__.test_results.append(result)

        # Summarize
        fails = [r for r in self.test_results if not r["passed"]]
        passes = [r for r in self.test_results if r["passed"]]

        print("\n================== Test Summary ==================")
        print(f"Total combos tested: {len(self.test_results)}")
        print(f"Failures: {len(fails)}")

        self.write_report_file(fails, passes)
        if fails:
            print("\n---- FAIL DETAILS ----")
            for f in fails:
                print(f"Test label: {f['label']}")
                print(f"Cmd: {f['cmd']}")
                print(f"Return code: {f['returncode']}")
                print(f"Stderr snippet: {f['stderr_snippet']}")
                print(f"Output check: {f.get('output_checks','')}")
                print("----------------------------------\n")

        # If any fail, fail the test suite
        self.assertEqual(len(fails), 0, f"Some SingleFile combos failed => {len(fails)} failed.")

    def write_report_file(self, fails, passes):
        """
        Writes a final report into self.report_file with details of pass/fail outcomes.
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
                checks = f_.get("output_checks", [])
                if checks:
                    lines.append("Output checks =>")
                    for c in checks:
                        lines.append(f"  - {c}")
                lines.append("-" * 40)
            lines.append("")
        lines.append("PASS DETAILS:")
        for p_ in passes:
            lines.append(f"Label: {p_['label']}")
            lines.append(f"Cmd: {p_['cmd']}")
            checks = p_.get("output_checks", [])
            if checks:
                lines.append("Output checks =>")
                for c in checks:
                    lines.append(f"  - {c}")
            lines.append("-" * 40)

        with open(self.report_file, "w", encoding="utf-8") as rf:
            rf.write("\n".join(lines))

        print(f"[INFO] Full test report written to: {self.report_file}")


if __name__ == "__main__":
    unittest.main(argv=[""], verbosity=2, exit=True)
