#!/usr/bin/env python3
"""Run fast, dependency-free repository checks used by every Actions route."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT = REPO_ROOT / "examples" / "esp-idf"
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
REMOTE_SCHEMES = {"http", "https", "mailto", "tel", "data"}
EXCLUDED_DIRECTORY_NAMES = {".git", "build", "managed_components", "__pycache__"}
REQUIRED_PAIRS = (
    ("README.md", "README_ZH.md"),
    ("CONTRIBUTING.md", "CONTRIBUTING_ZH.md"),
    ("SUPPORT.md", "SUPPORT_ZH.md"),
    ("docs/README.md", "docs/README_ZH.md"),
    ("docs/CI.md", "docs/CI_ZH.md"),
    ("docs/COMPONENTS.md", "docs/COMPONENTS_ZH.md"),
    ("docs/HARDWARE.md", "docs/HARDWARE_ZH.md"),
    (
        "examples/esp-idf/09_video_lcd_display/README.md",
        "examples/esp-idf/09_video_lcd_display/README_ZH.md",
    ),
    (
        "examples/esp-idf/10_mp4_player/README.md",
        "examples/esp-idf/10_mp4_player/README_ZH.md",
    ),
    (
        "examples/esp-idf/11_esp_brookesia_phone/README.md",
        "examples/esp-idf/11_esp_brookesia_phone/README_ZH.md",
    ),
)
REQUIRED_CI_DEFAULTS = (
    "config/ci/rgb888.defaults",
    "config/ci/usb_rgb888.defaults",
    "config/ci/brookesia_ai.defaults",
    "config/ci/usb_minimal.defaults",
)
REQUIRED_HOMEPAGE_COMPONENTS = {
    "centered_header",
    "html_h1",
    "subtitle",
    "badges",
    "language_switch",
    "quick_links",
    "hero_image",
    "separator",
    "h2",
}
REQUIRED_HOMEPAGE_QUICK_LINKS = {"product", "documentation", "firmware", "esp_idf"}
REQUIRED_HOMEPAGE_BADGES = {"build", "license"}
REQUIRED_HOMEPAGE_H2_ICONS = ["✨", "🖥️", "📦", "🧪", "🛠️", "🗂️", "📚", "🤝", "📄"]


def direct_examples(repo_root: Path = REPO_ROOT) -> list[Path]:
    root = repo_root / "examples" / "esp-idf"
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and (path / "CMakeLists.txt").is_file() and (path / "main").is_dir()
    )


def markdown_targets(text: str) -> list[str]:
    targets: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in LINK_PATTERN.finditer(line):
            target = match.group(1).strip()
            if target.startswith("<") and ">" in target:
                target = target[1 : target.index(">")]
            else:
                target = target.split(maxsplit=1)[0]
            targets.append(target)
    return targets


def markdown_files(repo_root: Path = REPO_ROOT) -> list[Path]:
    return sorted(
        path
        for path in repo_root.rglob("*.md")
        if not EXCLUDED_DIRECTORY_NAMES.intersection(path.relative_to(repo_root).parts)
    )


def local_link_errors(repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    for markdown in markdown_files(repo_root):
        text = markdown.read_text(encoding="utf-8")
        for raw_target in markdown_targets(text):
            if not raw_target or raw_target.startswith("#"):
                continue
            parsed = urlsplit(raw_target)
            if parsed.scheme.lower() in REMOTE_SCHEMES or parsed.netloc:
                continue
            target = unquote(parsed.path).replace("\\", "/")
            if not target or "${" in target or "{{" in target:
                continue
            if target.startswith("/"):
                resolved = repo_root / target.lstrip("/")
            else:
                resolved = markdown.parent / target
            if not resolved.exists():
                relative_markdown = markdown.relative_to(repo_root).as_posix()
                errors.append(f"{relative_markdown}: missing local link target {raw_target!r}")
    return errors


def usb_audio_dependency_errors(manifest: str, cmake: str, tinyusb_config: str) -> list[str]:
    """Keep the optional UAC package outside the USB minimal build graph."""
    errors: list[str] = []
    required_manifest = (
        'espressif/usb_device_uac:\n'
        '    version: "1.2.0"\n'
        '    # Download for the opt-in UAC path; do not require it for minimal builds.\n'
        '    require: no'
    )
    if required_manifest not in manifest:
        errors.append("12_usb_extend_screen: usb_device_uac must stay optional in the manifest")

    required_cmake = (
        "if(CONFIG_UAC_AUDIO_ENABLE)\n"
        '    list (APPEND srcs "app_uac.c")\n'
        "    list(APPEND priv_requires espressif__usb_device_uac)\n"
        "endif()"
    )
    if required_cmake not in cmake or "PRIV_REQUIRES ${priv_requires}" not in cmake:
        errors.append("12_usb_extend_screen: UAC component link must remain conditional")

    required_private_definition = (
        "if(NOT CONFIG_UAC_AUDIO_ENABLE)\n"
        "    # The downloaded-but-unlinked UAC target still compiles under older IDF;\n"
        "    # only its translation unit needs TinyUSB audio declarations.\n"
        "    idf_component_get_property(uac_lib espressif__usb_device_uac COMPONENT_LIB)\n"
        "    if(TARGET ${uac_lib})\n"
        "        target_compile_definitions(${uac_lib} PRIVATE CFG_TUD_AUDIO=1)\n"
        "    endif()\n"
        "endif()"
    )
    if required_private_definition not in cmake:
        errors.append(
            "12_usb_extend_screen: disabled UAC needs a TARGET-guarded, target-private audio declaration"
        )

    required_audio_guard = (
        "#ifndef CFG_TUD_AUDIO\n"
        "#if CONFIG_UAC_AUDIO_ENABLE\n"
        "#define CFG_TUD_AUDIO             1\n"
        "#else\n"
        "#define CFG_TUD_AUDIO             0\n"
        "#endif\n"
        "#endif"
    )
    if required_audio_guard not in tinyusb_config:
        errors.append("12_usb_extend_screen: TinyUSB audio setting must allow a private override")
    return errors


def brookesia_ai_compatibility_errors(cmake: str, coze_source: str) -> list[str]:
    """Keep the GMF 0.6 C++ compatibility layer local to the optional AI path."""
    errors: list[str] = []
    required_cxx_flag = (
        'set(SRCS_CPP_COMPILE_FLAGS "-Wno-missing-field-initializers -Wno-format")\n'
        "if(CONFIG_ESP_BROOKESIA_ENABLE_AI_FRAMEWORK)\n"
        '    string(APPEND SRCS_CPP_COMPILE_FLAGS " -fpermissive")\n'
        "endif()"
    )
    if required_cxx_flag not in cmake:
        errors.append(
            "11_esp_brookesia_phone: AI profile requires a local C++ -fpermissive compatibility flag"
        )
    if "esp_gmf_afe_keep_awake" in coze_source:
        errors.append(
            "11_esp_brookesia_phone: GMF 0.6 source must not call esp_gmf_afe_keep_awake"
        )
    return errors


def homepage_policy_errors(audit_policy: object) -> list[str]:
    """Require the configured bilingual homepage to retain its single-product contract."""
    if not isinstance(audit_policy, dict):
        return ["Markdown audit policy must be a JSON object"]

    homepage_pairs = audit_policy.get("homepage_pairs")
    if not isinstance(homepage_pairs, list):
        return ["Markdown audit policy: missing homepage_pairs list for README.md and README_ZH.md"]

    homepage = next(
        (
            pair
            for pair in homepage_pairs
            if isinstance(pair, dict)
            and pair.get("english") == "README.md"
            and pair.get("chinese") == "README_ZH.md"
        ),
        None,
    )
    if homepage is None:
        return ["Markdown audit policy: missing README.md/README_ZH.md single-product homepage pair"]

    errors: list[str] = []
    if homepage.get("profile") != "single-product":
        errors.append("Markdown audit policy: README homepage profile must be single-product")
    components = homepage.get("required_components")
    if not isinstance(components, list) or not REQUIRED_HOMEPAGE_COMPONENTS.issubset(components):
        errors.append("Markdown audit policy: README homepage must require its complete visual header and h2 components")
    quick_links = homepage.get("required_quick_links")
    if not isinstance(quick_links, list) or not REQUIRED_HOMEPAGE_QUICK_LINKS.issubset(quick_links):
        errors.append("Markdown audit policy: README homepage must require product, documentation, firmware, and esp_idf quick links")
    badges = homepage.get("required_badges")
    if not isinstance(badges, list) or not REQUIRED_HOMEPAGE_BADGES.issubset(badges):
        errors.append("Markdown audit policy: README homepage must require build and license badges")
    if homepage.get("required_h2_icons") != REQUIRED_HOMEPAGE_H2_ICONS:
        errors.append("Markdown audit policy: README homepage h2 icon order must match the bilingual homepage")
    if homepage.get("h3_emoji_allow_patterns") != []:
        errors.append("Markdown audit policy: README homepage h3 headings must use the default no-emoji policy")
    return errors


def repository_errors(repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    examples = direct_examples(repo_root)
    if len(examples) != 12:
        errors.append(f"expected 12 direct ESP-IDF product examples, found {len(examples)}")

    for english, chinese in REQUIRED_PAIRS:
        if not (repo_root / english).is_file():
            errors.append(f"missing required document: {english}")
        if not (repo_root / chinese).is_file():
            errors.append(f"missing required document: {chinese}")

    for relative in REQUIRED_CI_DEFAULTS:
        if not (repo_root / relative).is_file():
            errors.append(f"missing CI sdkconfig overlay: {relative}")

    audit_policy = repo_root / ".github" / "markdown-audit.json"
    try:
        policy = json.loads(audit_policy.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"invalid Markdown audit policy: {error}")
    else:
        errors.extend(homepage_policy_errors(policy))

    for example in examples:
        defaults = example / "sdkconfig.defaults"
        relative = defaults.relative_to(repo_root).as_posix()
        if not defaults.is_file():
            errors.append(f"{relative}: missing product sdkconfig.defaults")
            continue
        text = defaults.read_text(encoding="utf-8")
        if text.count("CONFIG_ESPTOOLPY_FLASHSIZE_32MB=y") != 1:
            errors.append(f"{relative}: expected exactly one 32MB flash selection")
        if "CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y" in text:
            errors.append(f"{relative}: conflicting 16MB flash selection")
        for stale_key in ("CONFIG_BSP_LCD_TYPE_HDMI", "CONFIG_BSP_LCD_TYPE_720_1280_7_INCH_A"):
            if stale_key in text:
                errors.append(f"{relative}: stale non-product setting {stale_key}")

    player_source = (
        repo_root / "examples" / "esp-idf" / "10_mp4_player" / "main" / "main.c"
    ).read_text(encoding="utf-8")
    for required in (
        "#if CONFIG_BSP_LCD_COLOR_FORMAT_RGB888",
        "APP_STREAM_JPEG_CONFIG_DEFAULT_RGB565()",
        "APP_STREAM_JPEG_CONFIG_DEFAULT_RGB888()",
        "DISPLAY_BYTES_PER_PIXEL",
    ):
        if required not in player_source:
            errors.append(f"10_mp4_player: missing conditional display path {required}")

    player_manifest = (
        repo_root / "examples" / "esp-idf" / "10_mp4_player" / "main" / "idf_component.yml"
    ).read_text(encoding="utf-8")
    if 'version: ">=2.3.0,<2.6.0"' not in player_manifest:
        errors.append(
            "10_mp4_player: esp_audio_codec must stay below v2.6 for pre-revision-3 P4 hardware"
        )

    usb_cmake = (
        repo_root / "examples" / "esp-idf" / "12_usb_extend_screen" / "main" / "CMakeLists.txt"
    ).read_text(encoding="utf-8")
    if usb_cmake.count('"app_uac.c"') != 1:
        errors.append("12_usb_extend_screen: app_uac.c must appear once in its conditional source list")
    usb_manifest = (
        repo_root
        / "examples"
        / "esp-idf"
        / "12_usb_extend_screen"
        / "main"
        / "idf_component.yml"
    ).read_text(encoding="utf-8")
    usb_tinyusb_config = (
        repo_root
        / "examples"
        / "esp-idf"
        / "12_usb_extend_screen"
        / "main"
        / "tusb"
        / "tusb_config_uac.h"
    ).read_text(encoding="utf-8")
    errors.extend(usb_audio_dependency_errors(usb_manifest, usb_cmake, usb_tinyusb_config))
    usb_main = (
        repo_root
        / "examples"
        / "esp-idf"
        / "12_usb_extend_screen"
        / "main"
        / "usb_extend_screen.c"
    ).read_text(encoding="utf-8")
    if "app_uac_init" in usb_main:
        errors.append("12_usb_extend_screen: UAC initialization must be owned by app_usb only")

    brookesia_cmake = (
        repo_root
        / "examples"
        / "esp-idf"
        / "11_esp_brookesia_phone"
        / "components"
        / "brookesia_core"
        / "CMakeLists.txt"
    ).read_text(encoding="utf-8")
    coze_source = (
        repo_root
        / "examples"
        / "esp-idf"
        / "11_esp_brookesia_phone"
        / "components"
        / "brookesia_core"
        / "ai_framework"
        / "agent"
        / "coze_chat_app.cpp"
    ).read_text(encoding="utf-8")
    errors.extend(brookesia_ai_compatibility_errors(brookesia_cmake, coze_source))

    firmware = sorted((repo_root / "firmware").glob("*.bin"))
    if len(firmware) != 1:
        errors.append(f"expected one immutable factory firmware binary, found {len(firmware)}")

    errors.extend(local_link_errors(repo_root))
    return errors


def main() -> int:
    errors = repository_errors()
    if errors:
        print("Repository audit failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"Repository audit passed: {len(direct_examples())} product examples, "
        f"{len(markdown_files())} Markdown files, local links valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
