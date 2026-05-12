from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = REPO_ROOT / "build"
DIST_DIR = REPO_ROOT / "dist"
SRC_DIR = REPO_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pivot.constants import APP_AUTHOR, APP_NAME, APP_VERSION  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Pivot with Nuitka.")
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Build standalone folder executable.",
    )
    parser.add_argument("--onefile", action="store_true", help="Build onefile executable.")
    parser.add_argument(
        "--portable-release",
        action="store_true",
        help="Emit outputs under dist/release/windows/portable",
    )
    parser.add_argument(
        "--icon",
        type=str,
        default="",
        help="Path to an .ico file for Windows executable icon.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    onefile = args.onefile or not args.standalone
    target_output_dir = DIST_DIR
    if args.portable_release:
        target_output_dir = DIST_DIR / "release" / "windows" / "portable"

    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--enable-plugin=pyside6",
        "--windows-console-mode=disable",
        f"--output-dir={target_output_dir}",
        "--output-filename=Pivot.exe",
        f"--company-name={APP_AUTHOR}",
        f"--product-name={APP_NAME}",
        f"--product-version={APP_VERSION}",
        f"--file-version={APP_VERSION}",
        "--file-description=Pivot desktop app",
        "--copyright=MIT",
        str(REPO_ROOT / "src" / "pivot" / "__main__.py"),
    ]
    if onefile:
        command.append("--onefile")
    icon_path = Path(args.icon).resolve() if args.icon else REPO_ROOT / "assets" / "pivot.ico"
    if icon_path.exists():
        command.append(f"--windows-icon-from-ico={icon_path}")

    BUILD_DIR.mkdir(exist_ok=True)
    target_output_dir.mkdir(parents=True, exist_ok=True)
    return subprocess.call(command, cwd=REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
