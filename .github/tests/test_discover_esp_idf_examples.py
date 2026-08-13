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

    def test_markdown_is_documentation_before_example_ownership(self) -> None:
        known = {"examples/esp-idf/01_demo", "examples/esp-idf/02_demo"}
        for path in (
            "README.md",
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
        for path in ("config/ci/rgb888.defaults", "scripts/ci_firmware.py", "Flash-CI-Firmware.sh", ".github/tests/test_ci_firmware.py", ".github/scripts/audit_markdown.py"):
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
                {"example": "examples/esp-idf/01_demo", "idf_version": "v5.5.5", "variant": "default", "sdkconfig_defaults": "", "artifact_name": "firmware-esp-idf-01-demo-v5.5.5-default"},
                {"example": "examples/esp-idf/01_demo", "idf_version": "v6.0.2", "variant": "default", "sdkconfig_defaults": "", "artifact_name": "firmware-esp-idf-01-demo-v6.0.2-default"},
            ]})
            values = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
            self.assertEqual(values["route"], "examples")
            self.assertEqual(values["examples"], "examples/esp-idf/01_demo")
            self.assertEqual(values["docs_only"], "false")
            self.assertEqual(values["build_count"], "2")

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
        self.assertEqual(len(matrix), 39)
        self.assertTrue(all(item["artifact_name"].startswith("firmware-esp-idf-") for item in matrix))
        self.assertEqual(len({item["artifact_name"] for item in matrix}), 39)
        self.assertEqual(sum(item["variant"] == "default" for item in matrix), 24)
        self.assertEqual(sum(item["variant"] == "rgb888" for item in matrix), 12)
        self.assertEqual(sum(item["variant"] == "ai" for item in matrix), 1)
        self.assertEqual(sum(item["variant"] == "minimal" for item in matrix), 2)
        self.assertEqual(
            [item["idf_version"] for item in matrix if item["variant"] == "ai"], ["v5.5.5"]
        )
        self.assertFalse(
            any(
                item["variant"] == "ai" and item["idf_version"] == "v6.0.2"
                for item in matrix
            )
        )


if __name__ == "__main__":
    unittest.main()
