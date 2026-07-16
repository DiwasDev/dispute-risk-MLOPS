# Agent Instructions (AGENTS.md)

This repository holds a production-grade MLOps system for predicting whether a consumer will dispute a complaint resolution.

## System Boundaries & Entry Points
- **API Service**: `app/main.py` (FastAPI). Start locally with:
  ```bash
  uvicorn app.main:app --reload
  ```
- **ML Pipelines**: Modular components split between `pipelines/` (orchestration) and `steps/` (pipeline step logic).
- **Core Library**: Reusable Python packages reside in `src/`. Do not write core algorithms directly in pipeline step files.
- **Docker**: Single-container setup via `Dockerfile` and `docker-compose.yml` for local API deployment.

## Toolchain & Commands
- **Python**: Requires `>=3.12`. A `venv/` is present at the root workspace. Ensure you activate it or use its binaries directly.
- **Dependencies**: Main dependencies are in `requirements.txt` and `pyproject.toml`.
- **Quality Gates**:
  - Code Style: `black .`
  - Linting: `ruff check .`
  - Testing: `pytest` (tests belong in `tests/`)
