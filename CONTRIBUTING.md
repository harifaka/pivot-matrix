# Contributing to Pivot

Thanks for contributing.

## Setup

1. Create and activate a virtual environment.
2. Install development dependencies:
   - `python -m pip install -r requirements-dev.txt`
3. Run validation before opening a PR:
   - `python -m ruff check .`
   - `python -m mypy src`
   - `python -m pytest`

## Pull request expectations

- keep changes focused and minimal
- include tests for behavior changes
- update docs when user-facing behavior changes
- avoid unrelated refactors in the same PR

## Quality bar

- no lint/type/test regressions
- no new persistence/data-loss risks
- no regressions in portable mode behavior
- maintain compatibility with Windows desktop release flow
