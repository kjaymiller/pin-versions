# pin-versions

A CLI tool and pre-commit hook that pins all unpinned dependencies in `pyproject.toml` to their currently installed versions.

## Installation

```bash
pip install pin-versions
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add pin-versions
```

## Usage

Run in a project directory with a `pyproject.toml` and a virtual environment:

```bash
pin-versions
```

This pins dependencies in `[project].dependencies`, `[project.optional-dependencies]`, and `[dependency-groups]`.

### Options

| Flag | Description |
|---|---|
| `--operator`, `-o` | Version pin operator (default: `==`). Supports `>=`, `~=`, etc. |
| `--pyproject`, `-p` | Path to `pyproject.toml` (default: `./pyproject.toml`) |
| `--venv` | Path to the virtual environment (default: `.venv`) |
| `--pin-latest` | Pin uninstalled packages to their latest version on PyPI |
| `--dry-run` | Preview changes without modifying the file |

### Pre-commit hook

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/kjaymiller/pin-versions
    rev: v0.1.0
    hooks:
      - id: pin-versions
```

## Contributing

1. Fork the repo and clone it locally.
2. Create a virtual environment and install the project in editable mode:
   ```bash
   uv venv && uv pip install -e ".[dev]"
   ```
3. Create a branch for your changes:
   ```bash
   git checkout -b my-feature
   ```
4. Make your changes and ensure they work by running:
   ```bash
   pin-versions --dry-run
   ```
5. Open a pull request against `main`.
