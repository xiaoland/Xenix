# AGENTS.md for `packages/ml-backend`

This package contains the Python ML backend for Xenix.

## Tech Stack

- **Runtime:** Python
- **API Framework:** FastAPI
- **Package Manager:** pdm (pyproject.toml is SSoT; export with `pdm export -f requirements --without-hashes` when pip files are needed)
- **Testing:** pytest

## Project Structure

```
packages/ml-backend/
├── ml_backend/          # App code
├── main.py              # Entry point
├── server.py            # Server runner (if present)
├── scripts/             # Utilities
├── tests/               # Pytest tests
├── docs/                # Package docs
└── pyproject.toml       # PDM config
```

## Development

- Install deps: `pdm install`
- Run tests: `pytest`
- Lint/format: follow project-wide tooling if configured in `pyproject.toml`.

## Coding Guidelines

- Keep ML logic in `ml_backend/` and avoid mixing server/bootstrap code with model code.
- Prefer JSON I/O between Node and Python services.
- Add/adjust tests in `tests/` for any behavior changes.
- Keep API routes typed and validated when possible.
