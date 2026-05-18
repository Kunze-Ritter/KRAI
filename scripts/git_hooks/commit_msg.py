#!/usr/bin/env python3
"""Git commit-msg hook for automated version updates."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_pre_commit_module() -> module:
    """Ensure the shared pre_commit module is importable and return it."""

    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "git_hooks" / "pre_commit.py"

    spec = importlib.util.spec_from_file_location("krai_git_hook_pre_commit", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - import failure path
        raise ImportError(f"Could not load pre_commit module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_commit_message(path: Path) -> str:
    """Return the commit message from the temporary file."""

    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8")


def main(args: list[str] | None = None) -> int:
    """Entrypoint for the commit-msg hook."""

    args = args if args is not None else sys.argv[1:]
    if not args:
        print("Warning: commit-msg hook expected path to commit message file", file=sys.stderr)
        return 0

    message_path = Path(args[0])
    commit_message = read_commit_message(message_path)

    version_file = Path("backend/processors/__version__.py")
    pre_commit = _load_pre_commit_module()

    try:
        pre_commit.update_version_file(
            version_file,
            commit_message,
            update_commit=False,
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        print(f"Warning: Error updating version file: {exc}", file=sys.stderr)
        return 0

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI behaviour
    sys.exit(main())
