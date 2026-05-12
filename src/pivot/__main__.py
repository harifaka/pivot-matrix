"""CLI entry point for Pivot."""

from __future__ import annotations

from pivot.bootstrap import run


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
