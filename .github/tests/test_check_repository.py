from __future__ import annotations

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
    def test_reviewed_bsp_pin_requires_exact_mapping(self) -> None:
        manifest = (
            "dependencies:\n"
            f"  {checks.BSP_COMPONENT}:\n"
            f"    git: {checks.BSP_PIN_FIELDS['git']}\n"
            f"    path: {checks.BSP_PIN_FIELDS['path']}\n"
            f"    version: {checks.BSP_PIN_FIELDS['version']}\n"
        )
        self.assertEqual(checks.pinned_bsp_dependency_errors(manifest), [])
        self.assertTrue(
            checks.pinned_bsp_dependency_errors(
                manifest.replace(checks.BSP_PIN_FIELDS["version"], "deadbeef")
            )
        )
        self.assertTrue(
            checks.pinned_bsp_dependency_errors(
                manifest.replace(f"  {checks.BSP_COMPONENT}:\n", f"  {checks.BSP_COMPONENT}: \"*\"\n")
            )
        )

    def test_bsp_policy_removes_base_copy_and_retains_extensions(self) -> None:
        manifest = (
            "dependencies:\n"
            f"  {checks.BSP_COMPONENT}:\n"
            f"    git: {checks.BSP_PIN_FIELDS['git']}\n"
            f"    path: {checks.BSP_PIN_FIELDS['path']}\n"
            f"    version: {checks.BSP_PIN_FIELDS['version']}\n"
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
