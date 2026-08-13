from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[2] / "releases" / "package_firmware.py"
SPEC = importlib.util.spec_from_file_location("package_firmware", SCRIPT)
assert SPEC and SPEC.loader
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)


class PackageFirmwareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "examples" / "esp-idf" / "01_Demo"
        (self.project / "main").mkdir(parents=True)
        (self.project / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.16)\n")
        self.build = self.project / "build"
        self.build.mkdir()
        (self.build / "boot.bin").write_bytes(b"boot")
        (self.build / "app.bin").write_bytes(b"application")
        (self.build / "flash_args").write_text("generated arguments\n")
        self.output = self.root / "out"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_flasher(
        self,
        flash_files: dict[str, str],
        extra_esptool_args: object = None,
        flash_settings: object = None,
    ) -> None:
        if extra_esptool_args is None:
            extra_esptool_args = {"before": "default_reset", "after": "hard_reset", "stub": True, "chip": "esp32p4"}
        if flash_settings is None:
            flash_settings = {"flash_mode": "dio", "compress": True}
        (self.build / "flasher_args.json").write_text(
            json.dumps({"flash_files": flash_files, "extra_esptool_args": extra_esptool_args, "flash_settings": flash_settings}),
            encoding="utf-8",
        )

    def package(self) -> Path:
        self.write_flasher({"0x1000": "boot.bin", "0x10000": "app.bin"})
        with patch.dict(os.environ, {"PACKAGE_GIT_SHA": "a" * 40, "PACKAGE_RUN_ID": "42"}, clear=False), patch.object(package.Path, "cwd", return_value=self.root):
            return package.package_esp_idf(self.project, self.build, "v5.5.5", "rgb888", self.output)

    def test_archive_manifest_helpers_and_hashes(self) -> None:
        output = self.package()
        self.assertEqual(output.name, "firmware-esp-idf-01-demo-v5.5.5-rgb888.zip")
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            self.assertTrue({"manifest.json", "flash.sh", "flash.bat", "metadata/flasher_args.json", "metadata/flash_args", "bin/boot.bin", "bin/app.bin"}.issubset(names))
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["board"], "ESP32-P4-WIFI6-Touch-LCD-4.3")
            self.assertEqual(manifest["chip"], "esp32p4")
            self.assertEqual(manifest["variant"], "rgb888")
            self.assertEqual(manifest["project_path"], "examples/esp-idf/01_Demo")
            self.assertEqual([item["offset"] for item in manifest["files"]], ["0x1000", "0x10000"])
            self.assertEqual(manifest["flash"]["esptool_args"], ["--before", "default_reset", "--after", "hard_reset", "--stub"])
            self.assertEqual(manifest["flash"]["write_args"], ["--flash_mode", "dio", "--compress"])
            self.assertEqual(manifest["git_sha"], "a" * 40)
            self.assertEqual(manifest["run_sha"], "a" * 40)
            self.assertEqual(manifest["run_id"], 42)
            self.assertEqual(manifest["flash_size_bytes"], 32 * 1024 * 1024)
            self.assertIn("--chip esp32p4", archive.read("flash.sh").decode())
            self.assertIn("0x10000", archive.read("flash.bat").decode())
            for item in manifest["files"]:
                self.assertEqual(package.sha256(Path(self.build / Path(item["archive_path"]).name)), item["sha256"])

    def test_idf_v6_hyphenated_reset_values_are_preserved(self) -> None:
        self.write_flasher(
            {"0x1000": "boot.bin"},
            {"before": "default-reset", "after": "hard-reset", "stub": False, "chip": "esp32p4"},
        )
        with patch.dict(os.environ, {"PACKAGE_GIT_SHA": "a" * 40, "PACKAGE_RUN_ID": "42"}, clear=False), patch.object(package.Path, "cwd", return_value=self.root):
            output = package.package_esp_idf(self.project, self.build, "v6.0.2", "default", self.output)
        with zipfile.ZipFile(output) as archive:
            manifest = json.loads(archive.read("manifest.json"))
        self.assertEqual(manifest["flash"]["esptool_args"], ["--before", "default-reset", "--after", "hard-reset"])

    def test_invalid_reset_values_are_rejected(self) -> None:
        for extra in (
            {"before": "soft-reset", "after": "hard_reset", "stub": False, "chip": "esp32p4"},
            {"before": "default_reset", "after": "soft-reset", "stub": False, "chip": "esp32p4"},
        ):
            with self.subTest(extra=extra):
                self.write_flasher({"0x1000": "boot.bin"}, extra)
                with patch.object(package.Path, "cwd", return_value=self.root):
                    with self.assertRaisesRegex(ValueError, "unsupported"):
                        package.package_esp_idf(self.project, self.build, "v6.0.2", "default", self.output)

    def test_idf_v5_rejects_hyphenated_reset_values(self) -> None:
        self.write_flasher(
            {"0x1000": "boot.bin"},
            {"before": "default-reset", "after": "hard-reset", "stub": False, "chip": "esp32p4"},
        )
        with patch.object(package.Path, "cwd", return_value=self.root):
            with self.assertRaisesRegex(ValueError, "unsupported"):
                package.package_esp_idf(self.project, self.build, "v5.5.5", "default", self.output)

    def test_rejects_traversal_and_outside_project(self) -> None:
        outside = self.root / "outside.bin"
        outside.write_bytes(b"outside")
        self.write_flasher({"0x1000": "../outside.bin"})
        with patch.object(package.Path, "cwd", return_value=self.root):
            with self.assertRaisesRegex(ValueError, "outside"):
                package.package_esp_idf(self.project, self.build, "v5.5.5", "default", self.output)
            with self.assertRaisesRegex(ValueError, "project"):
                package.package_esp_idf(self.root / "other", self.build, "v5.5.5", "default", self.output)

    def test_rejects_duplicate_overlap_and_range(self) -> None:
        cases = (
            ({"0x1000": "boot.bin", "4096": "app.bin"}, "duplicate"),
            ({"0x1000": "boot.bin", "0x1002": "app.bin"}, "overlapping"),
            ({"0x1ffffff": "app.bin"}, "unsafe"),
        )
        for files, error in cases:
            with self.subTest(files=files):
                self.write_flasher(files)
                with patch.object(package.Path, "cwd", return_value=self.root):
                    with self.assertRaisesRegex(ValueError, error):
                        package.package_esp_idf(self.project, self.build, "v5.5.5", "default", self.output)

    def test_sha_environment_precedence(self) -> None:
        with patch.dict(os.environ, {"PACKAGE_GIT_SHA": "b" * 40, "GITHUB_SHA": "c" * 40}, clear=False):
            self.assertEqual(package.manifest_git_sha(), "b" * 40)
        with patch.dict(os.environ, {"PACKAGE_GIT_SHA": "", "GITHUB_SHA": "c" * 40}, clear=False):
            self.assertEqual(package.manifest_git_sha(), "c" * 40)
        self.assertEqual(package.manifest_run_id.__name__, "manifest_run_id")
        with patch.dict(os.environ, {"PACKAGE_RUN_ID": "0"}, clear=False):
            with self.assertRaisesRegex(ValueError, "PACKAGE_RUN_ID"): package.manifest_run_id()

    def test_rejects_unsafe_metadata_segments_and_protected_arguments(self) -> None:
        for value in ("", "../escape", "nested/value", "nested\\value", "bad..segment", "bad\x00value"):
            with self.subTest(field="framework_version", value=value):
                with patch.object(package.Path, "cwd", return_value=self.root):
                    with self.assertRaisesRegex(ValueError, "unsafe"):
                        package.package_esp_idf(self.project, self.build, value, "default", self.output)
            with self.subTest(field="variant", value=value):
                with patch.object(package.Path, "cwd", return_value=self.root):
                    with self.assertRaisesRegex(ValueError, "unsafe"):
                        package.package_esp_idf(self.project, self.build, "v5.5.5", value, self.output)
        for extra, write, expected in ((["--chip", "esp32p4", "--port", "COM9"], [], "--port"), (["--chip", "esp32p4"], ["erase_flash"], "erase_flash")):
            with self.subTest(extra=extra, write=write):
                self.write_flasher({"0x1000": "boot.bin"}, extra, write)
                with patch.object(package.Path, "cwd", return_value=self.root):
                    with self.assertRaises(ValueError):
                        package.package_esp_idf(self.project, self.build, "v5.5.5", "default", self.output)

    def test_requires_one_matching_generated_chip_option(self) -> None:
        cases = (
            ({"chip": "esp32s3"}, "exactly one"),
            (["--chip"], "missing"),
            (["--chip", "esp32p4", "--chip", "esp32p4"], "exactly one"),
        )
        for extra, expected in cases:
            with self.subTest(extra=extra):
                self.write_flasher({"0x1000": "boot.bin"}, extra)
                with patch.object(package.Path, "cwd", return_value=self.root):
                    with self.assertRaises(ValueError):
                        package.package_esp_idf(self.project, self.build, "v5.5.5", "default", self.output)


if __name__ == "__main__":
    unittest.main()
