from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "discover_esp_idf_examples.py"
SPEC = importlib.util.spec_from_file_location("discover_esp_idf_examples", SCRIPT)
assert SPEC and SPEC.loader
discover = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = discover
SPEC.loader.exec_module(discover)


class DiscoveryTests(unittest.TestCase):
    def test_only_direct_product_projects_are_discovered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            direct = root / "examples" / "esp-idf" / "01_demo"
            nested = direct / "components" / "vendored" / "test_apps"
            firmware = root / "firmware" / "not_a_product_example"
            for project in (direct, nested, firmware):
                (project / "main").mkdir(parents=True)
                (project / "CMakeLists.txt").touch()

            self.assertEqual(discover.list_examples(root), ["examples/esp-idf/01_demo"])

    def test_docs_only_route_has_no_builds(self) -> None:
        route = discover.classify_paths(["README.md", "docs/CI_ZH.md"], {"examples/esp-idf/01_demo"})
        self.assertTrue(route.docs_only)
        self.assertEqual(route.kind, "docs")
        self.assertEqual(route.selected, ())

    def test_documentation_assets_are_narrow_and_match_the_markdown_policy(self) -> None:
        known = {"examples/esp-idf/01_demo", "examples/esp-idf/02_demo"}
        for path in discover.DOCUMENTATION_ASSET_PATTERNS:
            with self.subTest(path=path):
                route = discover.classify_paths([path], known)
                self.assertEqual(route.kind, "docs")
                self.assertTrue(route.docs_only)
                self.assertEqual(route.selected, ())

        route = discover.classify_paths(["assets/build-input.c"], known)
        self.assertEqual(route.kind, "unknown")
        self.assertEqual(route.selected, tuple(sorted(known)))

        policy = json.loads(
            (Path(__file__).parents[1] / "markdown-audit.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            set(policy["docs_only_allowed_patterns"]),
            set(discover.DOCUMENTATION_ASSET_PATTERNS),
        )

    def test_governance_route_has_no_builds_and_is_not_docs_only(self) -> None:
        known = {"examples/esp-idf/01_demo", "examples/esp-idf/02_demo"}
        for path in (
            ".gitignore",
            "LICENSE.txt",
            ".github/ISSUE_TEMPLATE/bug_report.yml",
            ".github/pull_request_template.md",
        ):
            with self.subTest(path=path):
                route = discover.classify_paths([path], known)
                self.assertEqual(route.kind, "non_build")
                self.assertFalse(route.docs_only)
                self.assertEqual(route.selected, ())

    def test_markdown_audit_policy_change_fails_closed_to_full_matrix(self) -> None:
        known = {"examples/esp-idf/01_demo", "examples/esp-idf/02_demo"}
        route = discover.classify_paths([".github/markdown-audit.json"], known)
        self.assertEqual(route.kind, "unknown")
        self.assertFalse(route.docs_only)
        self.assertEqual(route.selected, tuple(sorted(known)))
        self.assertEqual(route.unknown_paths, (".github/markdown-audit.json",))

    def test_markdown_is_documentation_before_example_ownership(self) -> None:
        known = {"examples/esp-idf/01_demo", "examples/esp-idf/02_demo"}
        for path in (
            "README.md",
            "releases/README.md",
            ".github/tests/README.md",
            "config/ci/README.md",
            "examples/esp-idf/01_demo/README.md",
            "examples/esp-idf/01_demo/components/bundled/README.md",
        ):
            with self.subTest(path=path):
                route = discover.classify_paths([path], known)
                self.assertEqual(route.kind, "docs")
                self.assertTrue(route.docs_only)
                self.assertEqual(route.selected, ())

    def test_firmware_is_reported_but_not_built(self) -> None:
        for path in (
            "firmware/README.md",
            "firmware/main/app.c",
            "firmware/factory.bin",
            "firmware/release.zip",
        ):
            with self.subTest(path=path):
                route = discover.classify_paths([path], {"examples/esp-idf/01_demo"})
                self.assertEqual(route.kind, "firmware")
                self.assertTrue(route.firmware_changes)
                self.assertTrue(route.release_review)
                self.assertFalse(route.docs_only)
                self.assertEqual(route.selected, ())

    def test_arduino_only_changes_do_not_select_idf_builds(self) -> None:
        route = discover.classify_paths(
            ["examples/arduino/examples/01_HelloWorld/01_HelloWorld.ino"],
            {"examples/esp-idf/01_demo"},
        )
        self.assertEqual(route.kind, "arduino")
        self.assertFalse(route.docs_only)
        self.assertEqual(route.selected, ())

    def test_arduino_readme_is_documentation_only(self) -> None:
        route = discover.classify_paths(
            ["examples/arduino/README.md"],
            {"examples/esp-idf/01_demo"},
        )
        self.assertEqual(route.kind, "docs")
        self.assertTrue(route.docs_only)
        self.assertEqual(route.selected, ())

    def test_missing_or_zero_push_base_selects_full_matrix(self) -> None:
        examples = {"examples/esp-idf/01_demo", "examples/esp-idf/02_demo"}
        for base in (None, "0" * 40):
            route = discover.discover_changed_route(base, "HEAD", examples)
            self.assertEqual(route.kind, "initial_push")
            self.assertEqual(route.selected, tuple(sorted(examples)))
            self.assertEqual(len(discover.build_matrix(route.selected)["include"]), 4)

    def test_direct_example_selects_only_its_parent(self) -> None:
        known = {"examples/esp-idf/01_demo", "examples/esp-idf/02_demo"}
        route = discover.classify_paths(
            ["examples/esp-idf/02_demo/main/app.c"], known
        )
        self.assertEqual(route.selected, ("examples/esp-idf/02_demo",))

    def test_mixed_docs_and_source_selects_only_the_source_example(self) -> None:
        known = {"examples/esp-idf/01_demo", "examples/esp-idf/02_demo"}
        route = discover.classify_paths(
            ["examples/esp-idf/01_demo/README.md", "examples/esp-idf/02_demo/main/app.c"], known
        )
        self.assertEqual(route.selected, ("examples/esp-idf/02_demo",))
        self.assertFalse(route.docs_only)

    def test_global_ci_input_selects_all(self) -> None:
        known = {"examples/esp-idf/01_demo", "examples/esp-idf/02_demo"}
        for path in ("config/ci/rgb888.defaults", "releases/package_firmware.py", "scripts/ci_firmware.py", "Flash-CI-Firmware.sh", ".github/tests/test_ci_firmware.py", ".github/scripts/audit_markdown.py"):
            with self.subTest(path=path):
                route = discover.classify_paths([path], known)
                self.assertEqual(route.kind, "global")
                self.assertEqual(route.selected, tuple(sorted(known)))

    def test_unknown_path_selects_all_conservatively(self) -> None:
        known = {"examples/esp-idf/01_demo", "examples/esp-idf/02_demo"}
        route = discover.classify_paths(["tools/new-generator.py"], known)
        self.assertEqual(route.kind, "unknown")
        self.assertEqual(route.unknown_paths, ("tools/new-generator.py",))
        self.assertEqual(route.selected, tuple(sorted(known)))

    def test_empty_diff_fails_closed(self) -> None:
        with self.assertRaises(discover.RoutingError):
            discover.classify_paths([], {"examples/esp-idf/01_demo"})

    def test_rename_routes_both_old_and_new_paths(self) -> None:
        self.assertEqual(
            discover.paths_from_name_status(["R100\told.md\tdocs/new.md"]),
            ["docs/new.md", "old.md"],
        )

    def test_rename_and_delete_keep_their_old_path_impact(self) -> None:
        known = {"examples/esp-idf/01_demo"}
        paths = discover.paths_from_name_status([
            "R100\texamples/esp-idf/01_demo/main/app.c\tdocs/moved.md",
            "D\texamples/esp-idf/01_demo/main/removed.c",
        ])
        route = discover.classify_paths(paths, known)
        self.assertEqual(route.selected, ("examples/esp-idf/01_demo",))

    def test_cli_base_and_head_route_writes_github_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "examples" / "esp-idf" / "01_demo"
            (project / "main").mkdir(parents=True)
            (project / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.16)\n", encoding="utf-8")
            (project / "main" / "app.c").write_text("void app_main(void) {}\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Synthetic Tests"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            (project / "main" / "app.c").write_text("void app_main(void) { }\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-am", "source change"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            output = root / "github-output"
            environment = {**os.environ, "GITHUB_OUTPUT": str(output)}
            process = subprocess.run(
                [sys.executable, str(SCRIPT), "--base-ref", base, "--head-ref", head],
                cwd=root,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(process.stdout), {"include": [
                {"example": "examples/esp-idf/01_demo", "idf_version": "v5.5.5", "variant": "default", "sdkconfig_defaults": "../../../config/ci/rev3_x.defaults", "artifact_name": "firmware-esp-idf-01-demo-v5.5.5-default"},
                {"example": "examples/esp-idf/01_demo", "idf_version": "v6.0.2", "variant": "default", "sdkconfig_defaults": "../../../config/ci/rev3_x.defaults", "artifact_name": "firmware-esp-idf-01-demo-v6.0.2-default"},
            ]})
            values = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
            self.assertEqual(values["route"], "examples", values)
            self.assertEqual(values["examples"], "examples/esp-idf/01_demo")
            self.assertEqual(values["docs_only"], "false")
            self.assertEqual(values["build_count"], "2")

    def test_cli_routing_contract_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()

            def write(relative: str, value: str | bytes) -> None:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(value, bytes):
                    path.write_bytes(value)
                else:
                    path.write_text(value, encoding="utf-8")

            base_files: dict[str, str | bytes] = {
                "README.md": "# Synthetic product\n",
                "examples/esp-idf/01_demo/CMakeLists.txt": "cmake_minimum_required(VERSION 3.16)\n",
                "examples/esp-idf/01_demo/main/app.c": "void app_main(void) {}\n",
                "examples/esp-idf/01_demo/main/keep.c": "void keep(void) {}\n",
                "examples/esp-idf/01_demo/main/removed.c": "void removed(void) {}\n",
                "examples/esp-idf/01_demo/README.md": "# Demo 01\n",
                "examples/esp-idf/02_demo/CMakeLists.txt": "cmake_minimum_required(VERSION 3.16)\n",
                "examples/esp-idf/02_demo/main/app.c": "void app_main(void) {}\n",
                ".github/workflows/esp-idf-examples.yml": "name: Synthetic\n",
                ".github/ISSUE_TEMPLATE/bug_report.yml": "name: Bug\n",
                ".github/markdown-audit.json": "{}\n",
                "LICENSE.txt": "Synthetic license\n",
                "assets/ESP32-P4-WIFI6-Touch-LCD-4.3-details-1.jpg": b"image-v1",
                "schematic/ESP32-P4-WIFI6-Touch-LCD-4.3-schematic.pdf": b"pdf-v1",
                "firmware/README.md": "# Firmware\n",
                "firmware/main/app.c": "void factory(void) {}\n",
                "firmware/factory.bin": b"factory-v1",
                "firmware/release.zip": b"release-v1",
            }
            for relative, value in base_files.items():
                write(relative, value)

            subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Synthetic Tests"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            output = Path(directory) / "github-output"

            def run_route(base_ref: str, head_ref: str) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
                output.unlink(missing_ok=True)
                process = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--base-ref",
                        base_ref,
                        "--head-ref",
                        head_ref,
                    ],
                    cwd=root,
                    env={**os.environ, "GITHUB_OUTPUT": str(output)},
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                values = {}
                if output.is_file():
                    values = dict(
                        line.split("=", 1)
                        for line in output.read_text(encoding="utf-8").splitlines()
                    )
                return process, values

            cases = (
                (
                    "docs",
                    {
                        "README.md": "# Synthetic product docs update\n",
                        "examples/esp-idf/01_demo/README.md": "# Demo 01 docs update\n",
                        "assets/ESP32-P4-WIFI6-Touch-LCD-4.3-details-1.jpg": b"image-v2",
                        "schematic/ESP32-P4-WIFI6-Touch-LCD-4.3-schematic.pdf": b"pdf-v2",
                    },
                    {"route": "docs", "docs_only": "true", "has_examples": "false", "build_count": "0"},
                ),
                (
                    "governance",
                    {
                        ".github/ISSUE_TEMPLATE/bug_report.yml": "name: Better bug report\n",
                        "LICENSE.txt": "Synthetic license update\n",
                    },
                    {"route": "non_build", "docs_only": "false", "has_examples": "false", "build_count": "0"},
                ),
                (
                    "audit_policy",
                    {".github/markdown-audit.json": "{\"policy\": true}\n"},
                    {
                        "route": "unknown",
                        "docs_only": "false",
                        "unknown_paths": ".github/markdown-audit.json",
                        "build_count": "4",
                    },
                ),
                (
                    "direct_source",
                    {"examples/esp-idf/01_demo/main/app.c": "void app_main(void) { }\n"},
                    {"route": "examples", "examples": "examples/esp-idf/01_demo", "build_count": "2"},
                ),
                (
                    "global_input",
                    {".github/workflows/esp-idf-examples.yml": "name: Synthetic updated\n"},
                    {"route": "global", "build_count": "4"},
                ),
                (
                    "firmware_scope",
                    {
                        "firmware/README.md": "# Firmware update\n",
                        "firmware/main/app.c": "void factory(void) { }\n",
                        "firmware/factory.bin": b"factory-v2",
                        "firmware/release.zip": b"release-v2",
                    },
                    {
                        "route": "firmware",
                        "firmware_changes": "true",
                        "release_review": "true",
                        "has_examples": "false",
                        "docs_only": "false",
                        "build_count": "0",
                    },
                ),
                (
                    "unknown_asset",
                    {"assets/build-input.c": "void build_input(void) {}\n"},
                    {"route": "unknown", "unknown_paths": "assets/build-input.c", "build_count": "4"},
                ),
            )

            for index, (name, changes, expected) in enumerate(cases):
                with self.subTest(case=name):
                    subprocess.run(
                        ["git", "checkout", "-B", f"case-{index}", base],
                        cwd=root,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    for relative, value in changes.items():
                        write(relative, value)
                    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
                    subprocess.run(
                        ["git", "commit", "-m", name],
                        cwd=root,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
                    process, values = run_route(base, head)
                    self.assertEqual(process.returncode, 0, process.stderr)
                    self.assertEqual(json.loads(process.stdout), json.loads(values["matrix"]))
                    for key, value in expected.items():
                        self.assertEqual(values[key], value)

            subprocess.run(
                ["git", "checkout", "-B", "case-rename-delete", base],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            (root / "docs").mkdir(exist_ok=True)
            subprocess.run(
                ["git", "mv", "examples/esp-idf/01_demo/main/app.c", "docs/moved.md"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "rm", "examples/esp-idf/01_demo/main/removed.c"],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                ["git", "commit", "-m", "rename and delete"],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            process, values = run_route(base, head)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(values["route"], "examples", values)
            self.assertEqual(values["examples"], "examples/esp-idf/01_demo")
            self.assertEqual(values["build_count"], "2")

            process, _ = run_route(base, base)
            self.assertEqual(process.returncode, 2)
            self.assertIn("Git diff produced no changed paths", process.stderr)

            process, _ = run_route("refs/heads/missing", base)
            self.assertEqual(process.returncode, 2)
            self.assertIn("Unable to determine a safe CI route", process.stderr)

    def test_full_matrix_has_default_and_conditional_lanes(self) -> None:
        self.assertEqual(discover.DEFAULT_IDF_VERSIONS, ("v5.5.5", "v6.0.2"))
        examples = [
            f"examples/esp-idf/{name}"
            for name in (
                "01_HowToCreateProject",
                "02_HelloWorld",
                "03_i2c_tools",
                "04_wifistation",
                "05_sdmmc",
                "06_I2SCodec",
                "07_Displaycolorbar",
                "08_lvgl_demo_v9",
                "09_video_lcd_display",
                "10_mp4_player",
                "11_esp_brookesia_phone",
                "12_usb_extend_screen",
            )
        ]
        matrix = discover.build_matrix(examples)["include"]
        self.assertEqual(len(matrix), 41)
        self.assertTrue(all(item["artifact_name"].startswith("firmware-esp-idf-") for item in matrix))
        self.assertEqual(len({item["artifact_name"] for item in matrix}), 41)
        self.assertEqual(sum(item["variant"] == "default" for item in matrix), 24)
        self.assertEqual(sum(item["variant"] == "echo" for item in matrix), 2)
        self.assertEqual(sum(item["variant"] == "rgb888" for item in matrix), 12)
        self.assertEqual(sum(item["variant"] == "ai" for item in matrix), 1)
        self.assertEqual(sum(item["variant"] == "minimal" for item in matrix), 2)
        self.assertEqual(
            [item["idf_version"] for item in matrix if item["variant"] == "ai"],
            ["v5.5.5"],
        )
        self.assertEqual(
            [item["idf_version"] for item in matrix if item["variant"] == "echo"],
            ["v5.5.5", "v6.0.2"],
        )


if __name__ == "__main__":
    unittest.main()
