#!/usr/bin/env python3
"""Route repository changes to the ESP-IDF build matrix.

Only direct children of ``examples/esp-idf`` are product examples. Nested
projects belong to vendored components or their test suites and are not
promoted to product CI jobs.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


EXAMPLES_ROOT = PurePosixPath("examples/esp-idf")
DEFAULT_IDF_VERSIONS = ("v5.5.5", "v6.0.2")
GLOBAL_BUILD_PATTERNS = (
    ".github/workflows/esp-idf-examples.yml",
    ".github/scripts/discover_esp_idf_examples.py",
    ".github/scripts/audit_markdown.py",
    ".github/scripts/check_repository.py",
    ".github/tests/**",
    "config/ci/**",
    "releases/package_firmware.py",
    "Flash-CI-Firmware.cmd",
    "Flash-CI-Firmware.sh",
    "scripts/Flash-CI-Firmware.ps1",
    "scripts/ci_firmware.py",
)
DOCUMENTATION_ASSET_PATTERNS = (
    "assets/ESP32-P4-WIFI6-Touch-LCD-4.3-details-1.jpg",
    "schematic/ESP32-P4-WIFI6-Touch-LCD-4.3-schematic.pdf",
)
NON_BUILD_PATTERNS = (
    ".gitignore",
    "LICENSE",
    "LICENSE.txt",
    ".github/CODEOWNERS",
    ".github/FUNDING.yml",
    ".github/ISSUE_TEMPLATE/*.md",
    ".github/ISSUE_TEMPLATE/*.yml",
    ".github/ISSUE_TEMPLATE/*.yaml",
    ".github/pull_request_template.md",
)
FIRMWARE_PATTERNS = ("firmware/**", "Firmware/**", "FirmWare/**")

# Extra lanes are intentionally small and target conditional code that the
# default sdkconfig does not compile. Paths are relative to each example.
RGB888_EXAMPLES = {
    "07_Displaycolorbar",
    "08_lvgl_demo_v9",
    "09_video_lcd_display",
    "10_mp4_player",
    "11_esp_brookesia_phone",
    "12_usb_extend_screen",
}


class RoutingError(RuntimeError):
    """The changed-file scope cannot be determined safely."""


@dataclass(frozen=True)
class Route:
    selected: tuple[str, ...]
    kind: str
    docs_only: bool = False
    firmware_changes: bool = False
    release_review: bool = False
    unknown_paths: tuple[str, ...] = ()


def run_git(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [line.rstrip("\n") for line in result.stdout.splitlines() if line.strip()]


def is_project(path: Path) -> bool:
    return (path / "CMakeLists.txt").is_file() and (path / "main").is_dir()


def list_examples(repo_root: Path = Path(".")) -> list[str]:
    root = repo_root / EXAMPLES_ROOT
    if not root.is_dir():
        return []

    examples = [
        (EXAMPLES_ROOT / path.name).as_posix()
        for path in root.iterdir()
        if path.is_dir() and is_project(path)
    ]
    return sorted(examples)


def normalize_path(value: str) -> str:
    return PurePosixPath(value.strip().replace("\\", "/").strip("/")).as_posix()


def normalize_example(value: str, known_examples: set[str]) -> str:
    value = value.strip().strip("/")
    if not value or value == "all":
        return value

    normalized = normalize_path(value)
    if normalized in known_examples:
        return normalized

    matches = [example for example in known_examples if PurePosixPath(example).name == value]
    if len(matches) == 1:
        return matches[0]

    return normalized


def matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def paths_from_name_status(lines: list[str]) -> list[str]:
    """Expand git --name-status output, retaining both sides of renames."""
    paths: list[str] = []
    for line in lines:
        fields = line.split("\t")
        if len(fields) < 2:
            raise RoutingError(f"Malformed git diff record: {line!r}")
        status = fields[0]
        record_paths = fields[1:]
        if status.startswith(("R", "C")):
            if len(record_paths) != 2:
                raise RoutingError(f"Malformed rename/copy record: {line!r}")
        elif len(record_paths) != 1:
            raise RoutingError(f"Malformed git diff record: {line!r}")
        paths.extend(normalize_path(path) for path in record_paths)
    return sorted(dict.fromkeys(paths))


def example_for_path(path: str, known_examples: set[str]) -> str | None:
    for example in sorted(known_examples):
        if path == example or path.startswith(example + "/"):
            return example
    return None


def classify_paths(paths: list[str], known_examples: set[str]) -> Route:
    if not paths:
        raise RoutingError("Git diff produced no changed paths; refusing to guess a build scope.")

    selected: set[str] = set()
    unknown: set[str] = set()
    docs = False
    firmware = False
    global_build = False
    non_build = False

    for raw_path in paths:
        path = normalize_path(raw_path)
        if matches_any(path, FIRMWARE_PATTERNS):
            firmware = True
        elif matches_any(path, NON_BUILD_PATTERNS):
            non_build = True
        elif path.lower().endswith(".md") or matches_any(path, DOCUMENTATION_ASSET_PATTERNS):
            docs = True
        elif matches_any(path, GLOBAL_BUILD_PATTERNS):
            global_build = True
        else:
            example = example_for_path(path, known_examples)
            if example:
                selected.add(example)
            else:
                unknown.add(path)

    if global_build or unknown:
        selected = set(known_examples)

    if unknown:
        kind = "unknown"
    elif global_build:
        kind = "global"
    elif selected:
        kind = "examples"
    elif firmware:
        kind = "firmware"
    elif docs and not non_build:
        kind = "docs"
    else:
        kind = "non_build"

    docs_only = (
        docs
        and not non_build
        and not selected
        and not firmware
        and not unknown
        and not global_build
    )
    return Route(
        selected=tuple(sorted(selected)),
        kind=kind,
        docs_only=docs_only,
        firmware_changes=firmware,
        release_review=firmware,
        unknown_paths=tuple(sorted(unknown)),
    )


def discover_changed_route(base_ref: str | None, head_ref: str, known_examples: set[str]) -> Route:
    if base_ref:
        diff_args = ["diff", "--name-status", "--find-renames", f"{base_ref}...{head_ref}"]
    else:
        diff_args = [
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-status",
            "--find-renames",
            "-r",
            head_ref,
        ]
    return classify_paths(paths_from_name_status(run_git(diff_args)), known_examples)


def variants_for_example(example: str, idf_version: str) -> tuple[tuple[str, str], ...]:
    name = PurePosixPath(example).name
    variants: list[tuple[str, str]] = [("default", "")]
    if name == "06_I2SCodec":
        variants.append(("echo", "../../../config/ci/i2s_echo.defaults"))
    if name in RGB888_EXAMPLES:
        overlay = "usb_rgb888.defaults" if name == "12_usb_extend_screen" else "rgb888.defaults"
        variants.append(("rgb888", f"../../../config/ci/{overlay}"))
    if name == "11_esp_brookesia_phone":
        variants.append(("ai", "../../../config/ci/brookesia_ai.defaults"))
    if name == "12_usb_extend_screen":
        variants.append(("minimal", "../../../config/ci/usb_minimal.defaults"))
    return tuple(variants)


def build_matrix(selected: list[str] | tuple[str, ...]) -> dict[str, list[dict[str, str]]]:
    include: list[dict[str, str]] = []
    for example in selected:
        for idf_version in DEFAULT_IDF_VERSIONS:
            for variant, sdkconfig_defaults in variants_for_example(example, idf_version):
                slug = re.sub(r"[^a-z0-9]+", "-", PurePosixPath(example).name.lower()).strip("-")
                include.append(
                    {
                        "example": example,
                        "idf_version": idf_version,
                        "variant": variant,
                        "sdkconfig_defaults": sdkconfig_defaults,
                        "artifact_name": f"firmware-esp-idf-{slug}-{idf_version}-{variant}",
                    }
                )
    return {"include": include}


def github_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def emit(route: Route) -> None:
    matrix = build_matrix(route.selected)
    values = {
        "matrix": json.dumps(matrix, separators=(",", ":")),
        "has_examples": "true" if route.selected else "false",
        "examples": ",".join(route.selected),
        "route": route.kind,
        "docs_only": str(route.docs_only).lower(),
        "firmware_changes": str(route.firmware_changes).lower(),
        "release_review": str(route.release_review).lower(),
        "unknown_paths": ",".join(route.unknown_paths),
        "build_count": str(len(matrix["include"])),
    }
    for name, value in values.items():
        github_output(name, value)
    print(values["matrix"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--example", default="")
    args = parser.parse_args()

    known_examples = set(list_examples())
    if not known_examples:
        print("No direct ESP-IDF product examples were found.", file=sys.stderr)
        return 2

    requested_example = normalize_example(args.example, known_examples)
    try:
        if requested_example == "all":
            route = Route(tuple(sorted(known_examples)), "manual")
        elif requested_example:
            if requested_example not in known_examples:
                print(f"Unknown ESP-IDF example: {args.example}", file=sys.stderr)
                print("Known examples:", file=sys.stderr)
                for example in sorted(known_examples):
                    print(f"  {example}", file=sys.stderr)
                return 1
            route = Route((requested_example,), "manual")
        else:
            route = discover_changed_route(args.base_ref, args.head_ref, known_examples)
    except (RoutingError, subprocess.CalledProcessError) as error:
        print(f"Unable to determine a safe CI route: {error}", file=sys.stderr)
        return 2

    emit(route)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
