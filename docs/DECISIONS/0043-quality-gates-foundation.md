# 0043. Quality gates foundation

## Status

Accepted

## Context

- CI already runs Django checks, missing migration checks, migrations, tests,
  Docker smoke, and healthz.
- The repo does not yet have a Python lint/format gate.
- The project is growing enough that style drift and import/order issues are
  becoming costly.
- The repo has no `pyproject.toml` yet.
- Runtime dependencies should stay separate from development-only tools.

## Decision

- Add Ruff as the first Python quality gate.
- Use Ruff for both linting and formatting.
- Add `requirements-dev.txt` for development-only tooling.
- Add pre-commit hooks for local enforcement.
- Add CI quality checks for `ruff check .` and `ruff format --check .`.
- Keep Black, mypy, and coverage thresholds out of this slice.

## Consequences

Positive:

- CI catches syntax/lint/import/format drift earlier.
- Developers get fast local checks.
- Runtime dependencies stay clean.

Negative:

- Initial formatting/import cleanup may touch multiple Python files.
- Rules are intentionally conservative and do not catch deeper type/design
  issues.

Follow-up:

- Coverage reporting, no threshold at first.
- mypy/Django typing evaluation.
- More Ruff rules after the baseline stabilizes.
- Possible dedicated formatting-only cleanup slice if the first pass is too
  broad.
