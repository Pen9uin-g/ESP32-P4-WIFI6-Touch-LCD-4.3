from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "check_repository.py"
SPEC = importlib.util.spec_from_file_location("check_repository", SCRIPT)
assert SPEC and SPEC.loader
checks = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checks
SPEC.loader.exec_module(checks)


class RepositoryCheckTests(unittest.TestCase):
    def test_bundled_arduino_libraries_keep_versions_sources_and_licenses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            libraries = root / "examples/arduino/libraries"
            for name, requirement in checks.ARDUINO_LIBRARY_REQUIREMENTS.items():
                library = libraries / name
                library.mkdir(parents=True)
                (library / "library.properties").write_text(
                    f"name={name}\nversion={requirement['version']}\n",
                    encoding="utf-8",
                )
                for relative in requirement["files"]:
                    path = library / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
            (libraries / "lv_conf.h").write_text(
                "\n".join(checks.ARDUINO_LV_CONF_MARKERS) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(checks.bundled_arduino_library_errors(root), [])

            missing = libraries / "lvgl/src/core/lv_obj.c"
            missing.unlink()
            errors = checks.bundled_arduino_library_errors(root)
            self.assertTrue(any("missing bundled library file" in error for error in errors))

            properties = libraries / "GFX_Library_for_Arduino/library.properties"
            properties.write_text("version=9.9.9\n", encoding="utf-8")
            errors = checks.bundled_arduino_library_errors(root)
            self.assertTrue(any("expected bundled version 1.6.0" in error for error in errors))

    def test_required_ci_helpers_fail_closed_when_workflow_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in checks.REQUIRED_CI_HELPERS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            self.assertEqual(checks.required_ci_helper_errors(root), [])

            missing = ".github/workflows/arduino-examples.yml"
            (root / missing).unlink()
            self.assertEqual(
                checks.required_ci_helper_errors(root),
                [f"missing CI helper: {missing}"],
            )

    def test_factory_firmware_identity_locks_path_size_and_sha256(self) -> None:
        payload = b"synthetic immutable factory image"
        digest = hashlib.sha256(payload).hexdigest()
        expected = "firmware/product-FactoryOnly.bin"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / expected
            image.parent.mkdir(parents=True)
            image.write_bytes(payload)
            kwargs = {
                "expected_path": expected,
                "expected_size": len(payload),
                "expected_sha256": digest,
            }
            self.assertEqual(checks.factory_firmware_integrity_errors(root, **kwargs), [])

            image.write_bytes(payload + b"changed")
            errors = checks.factory_firmware_integrity_errors(root, **kwargs)
            self.assertTrue(any("immutable size changed" in error for error in errors))
            self.assertTrue(any("immutable SHA-256 changed" in error for error in errors))

            image.write_bytes(payload)
            (image.parent / "unexpected.bin").write_bytes(b"extra")
            errors = checks.factory_firmware_integrity_errors(root, **kwargs)
            self.assertTrue(any("sole immutable factory firmware" in error for error in errors))

    def test_published_bsp_pin_requires_exact_registry_mapping(self) -> None:
        manifest = (
            "dependencies:\n"
            f"  {checks.BSP_COMPONENT}:\n"
            f"    version: \"{checks.BSP_PIN_FIELDS['version']}\"\n"
        )
        self.assertEqual(checks.pinned_bsp_dependency_errors(manifest), [])
        self.assertTrue(
            checks.pinned_bsp_dependency_errors(
                manifest.replace(checks.BSP_PIN_FIELDS["version"], "^1.0.1")
            )
        )
        source_override = manifest.replace(
            "    version:",
            "    git: https://github.com/waveshareteam/Waveshare-ESP32-components.git\n"
            "    path: bsp/esp32_p4_wifi6_touch_lcd_4_3\n"
            "    version:",
        )
        self.assertTrue(checks.pinned_bsp_dependency_errors(source_override))
        self.assertTrue(
            checks.pinned_bsp_dependency_errors(
                manifest.replace(f"  {checks.BSP_COMPONENT}:\n", f"  {checks.BSP_COMPONENT}: \"*\"\n")
            )
        )

    def test_bsp_policy_removes_base_copy_and_retains_extensions(self) -> None:
        manifest = (
            "dependencies:\n"
            f"  {checks.BSP_COMPONENT}:\n"
            f"    version: \"{checks.BSP_PIN_FIELDS['version']}\"\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in checks.BSP_EXTRA_COMPONENT_DIRS:
                (root / relative).mkdir(parents=True)
            for relative in checks.BSP_MANIFESTS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(manifest, encoding="utf-8")
            self.assertEqual(checks.bsp_pin_policy_errors(root), [])

            (root / checks.BSP_BASE_COMPONENT_DIRS[0]).mkdir(parents=True)
            errors = checks.bsp_pin_policy_errors(root)
            self.assertTrue(any("local base BSP path must be absent" in error for error in errors))

            (root / checks.BSP_BASE_COMPONENT_DIRS[0]).rmdir()
            (root / checks.BSP_FORBIDDEN_EXTENSION_DIRS[0]).mkdir(parents=True)
            (root / checks.BSP_FORBIDDEN_EXTENSION_DIRS[0] / "CMakeLists.txt").touch()
            errors = checks.bsp_pin_policy_errors(root)
            self.assertTrue(any("unused product extension" in error for error in errors))

    def test_product_flash_size_is_unambiguous(self) -> None:
        relative = "examples/esp-idf/03_i2c_tools/sdkconfig.defaults"
        self.assertEqual(
            checks.flash_size_selection_errors("CONFIG_ESPTOOLPY_FLASHSIZE_32MB=y\n", relative),
            [],
        )
        for defaults in (
            "CONFIG_ESPTOOLPY_FLASHSIZE_2MB=y\nCONFIG_ESPTOOLPY_FLASHSIZE_32MB=y\n",
            "CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y\n",
            "",
        ):
            with self.subTest(defaults=defaults):
                self.assertTrue(checks.flash_size_selection_errors(defaults, relative))

    def test_sdkconfig_defaults_do_not_repeat_active_assignments(self) -> None:
        relative = "examples/esp-idf/03_i2c_tools/sdkconfig.defaults"
        self.assertEqual(
            checks.duplicate_sdkconfig_assignment_errors(
                "CONFIG_ESPTOOLPY_FLASHSIZE_32MB=y\nCONFIG_SPIRAM=y\n", relative
            ),
            [],
        )
        errors = checks.duplicate_sdkconfig_assignment_errors(
            "CONFIG_SPIRAM=y\nCONFIG_SPIRAM=n\n", relative
        )
        self.assertEqual(errors, [f"{relative}: repeated sdkconfig assignment CONFIG_SPIRAM"])

    def test_revision_profile_defaults_override_without_conflict(self) -> None:
        rev3 = (
            "CONFIG_ESP32P4_REV_MIN_300=y\n"
            "# CONFIG_ESP32P4_SELECTS_REV_LESS_V3 is not set\n"
            "CONFIG_SPIRAM=y\n"
            "CONFIG_SPIRAM_SPEED_250M=y\n"
            "# CONFIG_SPIRAM_SPEED_200M is not set\n"
        )
        rev1 = (
            "CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y\n"
            "CONFIG_ESP32P4_REV_MIN_100=y\n"
            "# CONFIG_ESP32P4_REV_MIN_300 is not set\n"
            "CONFIG_SPIRAM_SPEED_200M=y\n"
            "# CONFIG_SPIRAM_SPEED_250M is not set\n"
        )
        combined = checks.sdkconfig_assignments(f"{rev3}\n{rev1}")
        self.assertEqual(combined["CONFIG_ESP32P4_SELECTS_REV_LESS_V3"], "y")
        self.assertEqual(combined["CONFIG_ESP32P4_REV_MIN_100"], "y")
        self.assertEqual(combined["CONFIG_ESP32P4_REV_MIN_300"], "n")
        self.assertEqual(combined["CONFIG_SPIRAM_SPEED_200M"], "y")
        self.assertEqual(combined["CONFIG_SPIRAM_SPEED_250M"], "n")

    def test_wifi_password_is_not_logged(self) -> None:
        safe = "ESP_LOGI(TAG, \"connected to SSID:%s\", EXAMPLE_ESP_WIFI_SSID);\n"
        unsafe = (
            "ESP_LOGI(TAG, \"connected to SSID:%s password:%s\",\n"
            "         EXAMPLE_ESP_WIFI_SSID, EXAMPLE_ESP_WIFI_PASS);\n"
        )
        self.assertEqual(checks.wifi_public_log_errors(safe), [])
        self.assertTrue(checks.wifi_public_log_errors(unsafe))
        self.assertTrue(checks.wifi_public_log_errors('printf("%s", EXAMPLE_ESP_WIFI_PASS);\n'))
        self.assertEqual(
            checks.wifi_public_log_errors('// printf("%s", EXAMPLE_ESP_WIFI_PASS);\n'),
            [],
        )

    def test_i2s_codec_uses_public_board_codec_paths(self) -> None:
        source = "\n".join(
            (
                "#if CONFIG_EXAMPLE_MODE_ECHO",
                "bsp_audio_codec_speaker_init();",
                "bsp_audio_codec_microphone_init();",
                "esp_codec_dev_read(microphone, buffer, size);",
                "esp_codec_dev_write(speaker, buffer, size);",
                ".channel = 2,",
                ".channel_mask = 0x03,",
                "#endif",
            )
        )
        overlay = "CONFIG_EXAMPLE_MODE_ECHO=y\n"
        config = "#define EXAMPLE_MCLK_MULTIPLE (256)\n"
        self.assertEqual(checks.audio_bsp_contract_errors(source, overlay, config), [])
        self.assertTrue(
            checks.audio_bsp_contract_errors(source + "\nBSP_I2S_GPIO_CFG();\n", overlay, config)
        )
        self.assertTrue(checks.audio_bsp_contract_errors(source, "", config))
        self.assertTrue(
            checks.audio_bsp_contract_errors(
                source.replace(".channel = 2", ".channel = 1"), overlay, config
            )
        )
        comment_only = "/*\n" + source + "\n*/\n"
        self.assertTrue(checks.audio_bsp_contract_errors(comment_only, overlay, config))
        literal_only = 'const char *fake = "' + source.replace('"', '\\"').replace("\n", " ") + '";\n'
        self.assertTrue(checks.audio_bsp_contract_errors(literal_only, overlay, config))
        self.assertEqual(
            checks.audio_bsp_contract_errors(
                source + "\n// i2s_channel_read(fake);\n", overlay, config
            ),
            [],
        )
        self.assertTrue(checks.audio_bsp_contract_errors(source, overlay, config.replace("256", "384")))

    def test_usb_audio_dependency_boundary(self) -> None:
        manifest = (
            'espressif/usb_device_uac:\n'
            '    version: "1.2.0"\n'
            '    # Download for the opt-in UAC path; do not require it for minimal builds.\n'
            '    require: no\n'
        )
        main_cmake = (
            "if(CONFIG_UAC_AUDIO_ENABLE)\n"
            '    list (APPEND srcs "app_uac.c")\n'
            "    list(APPEND priv_requires espressif__usb_device_uac)\n"
            "endif()\n"
            "idf_component_register(PRIV_REQUIRES ${priv_requires})\n"
        )
        project_cmake = (
            "cmake_minimum_required(VERSION 3.16)\n"
            "project(usb_touch_screen)\n"
            "\n"
            "if(NOT CONFIG_UAC_AUDIO_ENABLE)\n"
            "    # project() creates managed component targets; an older IDF can still compile\n"
            "    # this downloaded-but-unlinked UAC target, so only it needs TinyUSB audio declarations.\n"
            "    idf_component_get_property(uac_lib espressif__usb_device_uac COMPONENT_LIB)\n"
            "    if(TARGET ${uac_lib})\n"
            "        target_compile_definitions(${uac_lib} PRIVATE CFG_TUD_AUDIO=1)\n"
            "    endif()\n"
            "endif()\n"
        )
        tinyusb_config = (
            "#ifndef CFG_TUD_AUDIO\n"
            "#if CONFIG_UAC_AUDIO_ENABLE\n"
            "#define CFG_TUD_AUDIO             1\n"
            "#else\n"
            "#define CFG_TUD_AUDIO             0\n"
            "#endif\n"
            "#endif\n"
        )
        self.assertEqual(
            checks.usb_audio_dependency_errors(manifest, main_cmake, project_cmake, tinyusb_config),
            [],
        )
        self.assertTrue(
            checks.usb_audio_dependency_errors(
                manifest.replace("    require: no\n", ""), main_cmake, project_cmake, tinyusb_config
            )
        )
        self.assertTrue(
            checks.usb_audio_dependency_errors(
                manifest,
                main_cmake.replace("    list(APPEND priv_requires espressif__usb_device_uac)\n", ""),
                project_cmake,
                tinyusb_config,
            )
        )
        self.assertTrue(
            checks.usb_audio_dependency_errors(
                manifest,
                main_cmake,
                project_cmake.replace(
                    "    target_compile_definitions(${uac_lib} PRIVATE CFG_TUD_AUDIO=1)\n", ""
                ),
                tinyusb_config,
            )
        )
        self.assertTrue(
            checks.usb_audio_dependency_errors(
                manifest,
                main_cmake,
                project_cmake.replace("    if(TARGET ${uac_lib})\n", ""),
                tinyusb_config,
            )
        )
        self.assertTrue(
            checks.usb_audio_dependency_errors(
                manifest,
                main_cmake,
                project_cmake.replace(
                    "cmake_minimum_required(VERSION 3.16)\nproject(usb_touch_screen)\n\n", ""
                )
                + "project(usb_touch_screen)\n",
                tinyusb_config,
            )
        )
        self.assertTrue(
            checks.usb_audio_dependency_errors(
                manifest,
                main_cmake
                + "target_compile_definitions(${uac_lib} PRIVATE CFG_TUD_AUDIO=1)\n",
                project_cmake,
                tinyusb_config,
            )
        )
        self.assertTrue(
            checks.usb_audio_dependency_errors(
                manifest,
                main_cmake,
                project_cmake,
                tinyusb_config.replace("#ifndef CFG_TUD_AUDIO\n", ""),
            )
        )

    def test_brookesia_ai_compatibility_boundary(self) -> None:
        cmake = (
            'set(SRCS_CPP_COMPILE_FLAGS "-Wno-missing-field-initializers -Wno-format")\n'
            "if(CONFIG_ESP_BROOKESIA_ENABLE_AI_FRAMEWORK)\n"
            '    string(APPEND SRCS_CPP_COMPILE_FLAGS " -fpermissive")\n'
            "endif()\n"
        )
        coze_source = "static void change_speaking_state(bool speaking) {}\n"
        self.assertEqual(checks.brookesia_ai_compatibility_errors(cmake, coze_source), [])
        self.assertTrue(
            checks.brookesia_ai_compatibility_errors(
                cmake.replace('    string(APPEND SRCS_CPP_COMPILE_FLAGS " -fpermissive")\n', ""),
                coze_source,
            )
        )
        self.assertTrue(
            checks.brookesia_ai_compatibility_errors(
                cmake,
                "esp_gmf_afe_keep_awake(audio_processor_get_afe_handle(), true);\n",
            )
        )

    def test_single_product_homepage_policy(self) -> None:
        policy = {
            "homepage_pairs": [
                {
                    "english": "README.md",
                    "chinese": "README_ZH.md",
                    "profile": "single-product",
                    "required_components": sorted(checks.REQUIRED_HOMEPAGE_COMPONENTS),
                    "required_quick_links": sorted(checks.REQUIRED_HOMEPAGE_QUICK_LINKS),
                    "required_badges": sorted(checks.REQUIRED_HOMEPAGE_BADGES),
                    "required_h2_icons": checks.REQUIRED_HOMEPAGE_H2_ICONS,
                    "h3_emoji_allow_patterns": [],
                }
            ]
        }
        self.assertEqual(checks.homepage_policy_errors(policy), [])
        policy["homepage_pairs"][0]["required_components"].remove("hero_image")
        self.assertTrue(checks.homepage_policy_errors(policy))
        policy["homepage_pairs"][0]["required_components"].append("hero_image")
        policy["homepage_pairs"][0]["required_quick_links"].remove("product")
        self.assertTrue(checks.homepage_policy_errors(policy))

    def test_markdown_targets_ignore_fenced_examples(self) -> None:
        text = "[real](docs/CI.md)\n```md\n[example](missing.md)\n```\n"
        self.assertEqual(checks.markdown_targets(text), ["docs/CI.md"])

    def test_local_link_check_reports_only_missing_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs" / "exists.md").write_text("ok", encoding="utf-8")
            (root / "README.md").write_text(
                "[ok](docs/exists.md) [web](https://example.com) [bad](missing.md)",
                encoding="utf-8",
            )
            errors = checks.local_link_errors(root)
            self.assertEqual(errors, ["README.md: missing local link target 'missing.md'"])

    def test_markdown_inventory_ignores_generated_trees(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "managed_components" / "vendor").mkdir(parents=True)
            (root / "docs" / "README.md").touch()
            (root / "managed_components" / "vendor" / "README.md").touch()
            self.assertEqual(
                [path.relative_to(root).as_posix() for path in checks.markdown_files(root)],
                ["docs/README.md"],
            )


if __name__ == "__main__":
    unittest.main()
