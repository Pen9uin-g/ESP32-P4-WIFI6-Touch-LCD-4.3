from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import sys
import tempfile
import unittest
import zipfile
import urllib.request
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[2]
CORE_PATH = ROOT / "scripts" / "ci_firmware.py"
SPEC = importlib.util.spec_from_file_location("ci_firmware", CORE_PATH)
assert SPEC and SPEC.loader
core = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = core
SPEC.loader.exec_module(core)


class FakeApi:
    def __init__(self, values: dict[str, object]):
        self.repo = "owner/repository"
        self.values = values

    def json(self, endpoint: str):
        for key, value in self.values.items():
            if key in endpoint:
                return value
        raise AssertionError(endpoint)


class CiFirmwareTests(unittest.TestCase):
    def test_origin_parsing_supported_forms_and_rejects_other_hosts(self) -> None:
        for value in ("https://github.com/owner/repository.git", "ssh://git@github.com/owner/repository.git", "git@github.com:owner/repository.git"):
            self.assertEqual(core.parse_github_origin(value), "owner/repository")
        for bad in ("https://example.invalid/owner/repository", "https://github.com/owner/repo?x=1", "git@github.com:owner/repo;bad"):
            with self.assertRaises(core.SafetyError): core.parse_github_origin(bad)

    def test_catalog_is_exact_authoritative_42_lane_names(self) -> None:
        names = {lane.artifact for lane in core.load_catalog(ROOT)}
        expected = set()
        examples = ("01_HowToCreateProject", "02_HelloWorld", "03_i2c_tools", "04_wifistation", "05_sdmmc", "06_I2SCodec", "07_Displaycolorbar", "08_lvgl_demo_v9", "09_video_lcd_display", "10_mp4_player", "11_esp_brookesia_phone", "12_usb_extend_screen")
        for example in examples:
            for version in ("v5.5.5", "v6.0.2"):
                expected.add(f"firmware-esp-idf-{example.lower().replace('_', '-')}-{version}-default")
        for example in ("07_Displaycolorbar", "08_lvgl_demo_v9", "09_video_lcd_display", "10_mp4_player", "11_esp_brookesia_phone", "12_usb_extend_screen"):
            for version in ("v5.5.5", "v6.0.2"):
                expected.add(f"firmware-esp-idf-{example.lower().replace('_', '-')}-{version}-rgb888")
        expected |= {
            "firmware-esp-idf-06-i2scodec-v5.5.5-echo",
            "firmware-esp-idf-06-i2scodec-v6.0.2-echo",
            "firmware-esp-idf-11-esp-brookesia-phone-v5.5.5-ai",
            "firmware-esp-idf-11-esp-brookesia-phone-v6.0.2-ai",
            "firmware-esp-idf-12-usb-extend-screen-v5.5.5-minimal",
            "firmware-esp-idf-12-usb-extend-screen-v6.0.2-minimal",
        }
        self.assertEqual(names, expected)
        self.assertEqual(len(names), 42)

    def test_auth_prefers_authenticated_gh_then_token_and_never_anonymous(self) -> None:
        self.assertEqual(core.auth_mode(lambda _: "gh", {}, lambda: True), ("gh", None))
        self.assertEqual(core.auth_mode(lambda _: None, {"GH_TOKEN": "secret"}), ("token", "secret"))
        with self.assertRaises(core.SafetyError):
            core.auth_mode(lambda _: None, {})

    def test_newest_run_has_no_old_success_fallback(self) -> None:
        old = {"id": 1, "head_branch": "topic", "head_sha": "a" * 40, "status": "completed", "conclusion": "success", "path": ".github/workflows/esp-idf-examples.yml", "created_at": "2026-01-01"}
        latest_bad = {**old, "id": 2, "head_sha": "b" * 40, "created_at": "2026-02-01"}
        api = FakeApi({"/runs?": {"workflow_runs": [old, latest_bad]}})
        with self.assertRaises(core.SafetyError):
            core.select_run(api, "topic", "a" * 40, None)
        with self.assertRaises(core.SafetyError):
            core.select_run(FakeApi({"/actions/runs/2": latest_bad}), "topic", "a" * 40, 2)

    def test_partial_coverage_is_rejected(self) -> None:
        lanes = core.load_catalog(ROOT)
        api = FakeApi({"/jobs?": {"jobs": [{"name": "Preflight and route changes", "conclusion": "success"}]}, "/artifacts?": {"artifacts": []}})
        with self.assertRaises(core.SafetyError):
            core.verify_run_coverage(api, 1, lanes)

    def test_complete_coverage_uses_the_authoritative_lane_count(self) -> None:
        lanes = core.load_catalog(ROOT)
        head = "a" * 40
        jobs = [
            {
                "name": "Preflight and route changes",
                "status": "completed",
                "conclusion": "success",
            },
            *[
                {"name": lane.job_name, "status": "completed", "conclusion": "success"}
                for lane in lanes
            ],
        ]
        artifacts = [
            {
                "name": lane.artifact,
                "size_in_bytes": 1,
                "expired": False,
                "workflow_run": {"id": 7, "head_sha": head},
            }
            for lane in lanes
        ]
        api = FakeApi({"/jobs?": {"jobs": jobs}, "/artifacts?": {"artifacts": artifacts}})
        self.assertEqual(core.verify_run_coverage(api, 7, lanes, head), artifacts)

    def test_zip_rejects_traversal_symlink_and_duplicate_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, writer in (("traversal", lambda z: z.writestr("../escape", "x")), ("duplicate", lambda z: (z.writestr("manifest.json", "{}"), z.writestr("manifest.json", "{}")))):
                path = root / f"{name}.zip"
                with zipfile.ZipFile(path, "w") as archive:
                    writer(archive)
                with self.assertRaises(core.SafetyError):
                    core.extract_zip_safely(path, root / name)
            path = root / "symlink.zip"
            info = zipfile.ZipInfo("manifest.json"); info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(info, "target")
            with self.assertRaises(core.SafetyError):
                core.extract_zip_safely(path, root / "symlink")

    def _package(self, root: Path, **changes: object) -> tuple[core.Lane, str]:
        lane = core.load_catalog(ROOT)[0]
        binary = root / "bin" / "app.bin"; binary.parent.mkdir(exist_ok=True); binary.write_bytes(b"abc")
        head = "a" * 40
        manifest = {"schema_version": 1, "board": core.BOARD, "chip": core.CHIP, "framework": "esp-idf", "framework_version": lane.version, "variant": lane.variant, "target": core.CHIP, "project_path": lane.project, "source_project": lane.project, "git_sha": head, "run_sha": head, "run_id": 42, "flash_size_bytes": core.MAX_FLASH_BYTES, "artifact_name": lane.artifact, "workflow": core.WORKFLOW, "flash": {"baud": core.BAUD, "esptool_args": ["--after", "hard_reset"], "write_args": ["--flash_mode", "dio"]}, "files": [{"archive_path": "bin/app.bin", "sha256": hashlib.sha256(b"abc").hexdigest(), "size": 3, "offset": "0x1000"}]}
        manifest.update(changes)
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return lane, head

    def test_manifest_rejects_hash_size_offsets_chip_and_protected_args(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); lane, head = self._package(root)
            self.assertEqual(len(core.validate_manifest(root, lane, head, 42)[0]), 1)
            (root / "bin" / "other.bin").write_bytes(b"d")
            app = {"archive_path": "bin/app.bin", "sha256": hashlib.sha256(b"abc").hexdigest(), "size": 3, "offset": "0x1000"}
            other = {"archive_path": "bin/other.bin", "sha256": hashlib.sha256(b"d").hexdigest(), "size": 1, "offset": "0x1001"}
            cases = [
                {"chip": "esp32c6"},
                {"flash": {"baud": core.BAUD, "esptool_args": ["--port", "COM1"], "write_args": []}},
                {"files": [{"archive_path": "bin/app.bin", "sha256": "0" * 64, "size": 3, "offset": "0x1000"}]},
                {"files": [{"archive_path": "bin/app.bin", "sha256": hashlib.sha256(b"abc").hexdigest(), "size": 3, "offset": hex(core.MAX_FLASH_BYTES)}]},
                {"files": [app, other]},
                {"files": [{**other, "offset": "0x2000"}, app]},
            ]
            for change in cases:
                lane, head = self._package(root, **change)
                with self.assertRaises(core.SafetyError):
                    core.validate_manifest(root, lane, head, 42)

    def test_manifest_run_id_flash_size_and_strict_arguments_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); lane, head = self._package(root)
            for change in ({"run_id": 43}, {"flash_size_bytes": 1}, {"flash": {"baud": core.BAUD, "esptool_args": ["payload"], "write_args": []}}):
                lane, head = self._package(root, **change)
                with self.assertRaises(core.SafetyError): core.validate_manifest(root, lane, head, 42)

    def test_manifest_accepts_both_idf_reset_dialects_and_rejects_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for esptool_args in (
                ["--before", "default_reset", "--after", "hard_reset"],
                ["--before", "default-reset", "--after", "hard-reset"],
            ):
                with self.subTest(esptool_args=esptool_args):
                    lane, head = self._package(root, flash={"baud": core.BAUD, "esptool_args": esptool_args, "write_args": ["--flash_mode", "dio"]})
                    self.assertEqual(len(core.validate_manifest(root, lane, head, 42)[0]), 1)
            lane, head = self._package(root, flash={"baud": core.BAUD, "esptool_args": ["--after", "soft-reset"], "write_args": ["--flash_mode", "dio"]})
            with self.assertRaises(core.SafetyError):
                core.validate_manifest(root, lane, head, 42)

    def test_empty_serial_selection_fails_closed_but_explicit_port_is_not_enumerated(self) -> None:
        with self.assertRaises(core.SafetyError): core.choose("port: ", [])
        self.assertEqual(core.select_serial_port("COM99", []), "COM99")

    def test_safe_redirect_removes_cross_host_authorization(self) -> None:
        handler = core.SafeRedirect()
        request = urllib.request.Request("https://api.github.com/a", headers={"Authorization": "Bearer secret"})
        cross = handler.redirect_request(request, None, 302, "", {}, "https://objects.github.com/b")
        same = handler.redirect_request(request, None, 302, "", {}, "https://api.github.com/b")
        self.assertIsNone(cross.get_header("Authorization")); self.assertEqual(same.get_header("Authorization"), "Bearer secret")
        with self.assertRaises(core.SafetyError): handler.redirect_request(request, None, 302, "", {}, "http://objects.github.com/b")

    def test_outer_artifact_wrapper_requires_one_expected_safe_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); inner = root / "inner.zip"
            with zipfile.ZipFile(inner, "w") as archive: archive.writestr("manifest.json", "{}")
            expected = "firmware-esp-idf-demo-v5.5.5-default"
            outer = root / "outer.zip"
            with zipfile.ZipFile(outer, "w") as archive: archive.write(inner, expected + ".zip")
            self.assertEqual(core.unwrap_artifact_zip(outer.read_bytes(), expected), inner.read_bytes())
            with zipfile.ZipFile(outer, "w") as archive: archive.write(inner, "wrong.zip")
            with self.assertRaises(core.SafetyError): core.unwrap_artifact_zip(outer.read_bytes(), expected)

    def test_zip_metadata_limits_and_strict_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "z.zip"
            with zipfile.ZipFile(path, "w") as archive: archive.writestr("manifest.json", "{}")
            with zipfile.ZipFile(path) as archive:
                with patch.object(core, "MAX_ZIP_ENTRY_BYTES", 1):
                    with self.assertRaises(core.SafetyError): core.checked_zip_infos(archive)
                archive.infolist()[0].flag_bits |= 1
                with self.assertRaises(core.SafetyError): core.checked_zip_infos(archive)
        self.assertEqual(core.validate_args(["--flash_mode", "dio", "--compress"], "flash.write_args"), ["--flash_mode", "dio", "--compress"])
        for value in ("--force", "--encrypt", "--erase-all", "payload"):
            with self.assertRaises(core.SafetyError): core.validate_args([value], "flash.write_args")

    def test_explicit_confirmation_and_one_item_contract(self) -> None:
        core.require_flash_confirmation("one", "COM1", lambda _: "FLASH one")
        with self.assertRaises(core.SafetyError):
            core.require_flash_confirmation("one", "COM1", lambda _: "yes")
        source = CORE_PATH.read_text(encoding="utf-8")
        self.assertIn("for offset, path in plan", source)
        self.assertIn("Type FLASH {artifact}", source)

    def test_wrapper_parity_routes_all_platforms_to_shared_core(self) -> None:
        cmd = (ROOT / "Flash-CI-Firmware.cmd").read_text(encoding="utf-8")
        powershell = (ROOT / "scripts" / "Flash-CI-Firmware.ps1").read_text(encoding="utf-8")
        shell = (ROOT / "Flash-CI-Firmware.sh").read_text(encoding="utf-8")
        self.assertIn("Flash-CI-Firmware.ps1", cmd)
        self.assertIn("ci_firmware.py", powershell)
        self.assertIn("ci_firmware.py", shell)
        self.assertIn("$SelfTest", powershell)
        self.assertIn("$ListOnly", powershell)
        self.assertIn("$List", powershell)
        self.assertIn("$Preflight", powershell)
        self.assertIn("$PreflightOnly", powershell)
        self.assertTrue(shell.startswith("#!/usr/bin/env sh"))


if __name__ == "__main__":
    unittest.main()
