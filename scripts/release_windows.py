from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
RELEASE_ROOT = DIST_DIR / "release" / "windows"
PORTABLE_MARKER_NAME = "pivot.portable"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and package Windows releases.")
    parser.add_argument("--icon", type=str, default="", help="Optional .ico path for Nuitka.")
    return parser.parse_args()


def build_onefile(icon: str) -> None:
    command = [sys.executable, str(REPO_ROOT / "scripts" / "build_nuitka.py"), "--onefile"]
    if icon:
        command.extend(["--icon", icon])
    result = subprocess.run(command, cwd=REPO_ROOT, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def find_executable() -> Path:
    direct = DIST_DIR / "Pivot.exe"
    if direct.exists():
        return direct
    candidates = sorted(DIST_DIR.glob("**/Pivot.exe"), reverse=True)
    if not candidates:
        raise FileNotFoundError("Pivot.exe not found in dist output.")
    return candidates[0]


def package_release(executable: Path) -> None:
    standard_dir = RELEASE_ROOT / "standard"
    portable_dir = RELEASE_ROOT / "portable"
    for folder in (standard_dir, portable_dir):
        folder.mkdir(parents=True, exist_ok=True)

    standard_exe = standard_dir / "Pivot.exe"
    portable_exe = portable_dir / "Pivot.exe"
    shutil.copy2(executable, standard_exe)
    shutil.copy2(executable, portable_exe)
    (portable_dir / PORTABLE_MARKER_NAME).write_text(
        "Create this marker to force app-relative portable storage.\n",
        encoding="utf-8",
    )

    _write_release_notes(standard_dir, portable=False)
    _write_release_notes(portable_dir, portable=True)
    _zip_directory(standard_dir, RELEASE_ROOT / "Pivot-windows-standard.zip")
    _zip_directory(portable_dir, RELEASE_ROOT / "Pivot-windows-portable.zip")


def _write_release_notes(path: Path, *, portable: bool) -> None:
    mode = "Portable" if portable else "Standard"
    storage = (
        "App-relative ./pivot-data directory"
        if portable
        else "%APPDATA%\\Pivot (or ~/.pivot on non-Windows)"
    )
    (path / "README.txt").write_text(
        f"{mode} release for Pivot.\n\nStorage mode: {storage}\nExecutable: Pivot.exe\n",
        encoding="utf-8",
    )


def _zip_directory(folder: Path, destination_zip: Path) -> None:
    with ZipFile(destination_zip, "w", compression=ZIP_DEFLATED) as archive:
        for file_path in folder.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, arcname=file_path.relative_to(folder))


def main() -> int:
    args = parse_args()
    build_onefile(args.icon)
    executable = find_executable()
    package_release(executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
