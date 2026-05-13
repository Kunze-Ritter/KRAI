#!/usr/bin/env python3
"""Shared version-management utilities for git hooks and tests."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_parent_commit_hash() -> str | None:
    """Return the short hash for the current HEAD (parent of the pending commit)."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.STDOUT,
            text=True,
        ).strip()
    except subprocess.CalledProcessError as exc:  # pragma: no cover - git failure path
        print(f"Warning: Could not get git hash: {exc}", file=sys.stderr)
        return None


def parse_version(version_string):
    """Parse semantic version string into (major, minor, patch)."""
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version_string)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    return None


def increment_version(version_string, commit_message):
    """
    Increment version based on commit message keywords.

    Keywords:
    - RELEASE: or MAJOR: -> Increment major (2.1.3 -> 3.0.0)
    - MINOR: or FEATURE: -> Increment minor (2.1.3 -> 2.2.0)
    - PATCH: or FIX: or BUGFIX: -> Increment patch (2.1.3 -> 2.1.4)
    - No keyword -> Keep version unchanged
    """
    if not commit_message:
        return version_string

    # Convert to uppercase for case-insensitive matching
    msg_upper = commit_message.upper()

    # Parse current version
    version_parts = parse_version(version_string)
    if not version_parts:
        print(f"Warning: Could not parse version '{version_string}'", file=sys.stderr)
        return version_string

    major, minor, patch = version_parts

    # Check for keywords
    if "RELEASE:" in msg_upper or "MAJOR:" in msg_upper:
        return f"{major + 1}.0.0"
    if "MINOR:" in msg_upper or "FEATURE:" in msg_upper:
        return f"{major}.{minor + 1}.0"
    if "PATCH:" in msg_upper or "FIX:" in msg_upper or "BUGFIX:" in msg_upper:
        return f"{major}.{minor}.{patch + 1}"

    # No keyword found, keep version unchanged
    return version_string


def _replace_or_append(content: str, pattern: str, replacement: str, anchor_pattern: str) -> tuple[str, bool]:
    """Replace a regex match or append after the anchor if missing."""

    if re.search(pattern, content):
        return re.sub(pattern, replacement, content), True

    anchor_match = re.search(anchor_pattern, content)
    if anchor_match:
        insertion_index = anchor_match.end()
        before = content[:insertion_index]
        after = content[insertion_index:]
        prefix = "" if before.endswith("\n") else "\n"
        return f"{before}{prefix}{replacement}\n{after.lstrip()}", False

    suffix = "\n" if not content.endswith("\n") else ""
    return f"{content}{suffix}{replacement}\n", False


def stage_version_file(version_file_path: Path) -> None:
    """Stage the updated version file if possible."""

    try:
        subprocess.run(
            ["git", "add", str(version_file_path)],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - git failure path
        print(f"Warning: Could not stage version file: {exc}", file=sys.stderr)


def update_version_file(
    version_file_path: Path,
    commit_message: str | None,
    *,
    commit_hash: str | None = None,
    update_commit: bool = True,
    update_date: bool = True,
    stage: bool = True,
) -> None:
    """Update version metadata using the provided commit context."""

    if not version_file_path.exists():
        print(f"Warning: Version file not found: {version_file_path}", file=sys.stderr)
        return

    content = version_file_path.read_text(encoding="utf-8")

    version_match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    if not version_match:
        print("Warning: Could not find __version__ in version file", file=sys.stderr)
        return

    current_version = version_match.group(1)
    normalized_message = commit_message.strip() if commit_message else None
    new_version = increment_version(current_version, normalized_message)
    current_date = datetime.now().strftime("%Y-%m-%d") if update_date else None

    existing_commit_match = re.search(r'__commit__\s*=\s*"([^"]*)"', content)
    existing_commit = existing_commit_match.group(1) if existing_commit_match else ""

    if update_commit and not commit_hash:
        commit_hash = get_parent_commit_hash()

    if update_commit:
        commit_value = commit_hash or existing_commit or "pending"
    else:
        commit_value = existing_commit or "pending"

    commit_replacement_line = f'__commit__ = "{commit_value}"'

    content, _ = _replace_or_append(
        content,
        r'__version__\s*=\s*"[^"]*"',
        f'__version__ = "{new_version}"',
        r'__version__\s*=\s*"[^"]*"',
    )

    content, _ = _replace_or_append(
        content,
        r'__commit__\s*=\s*"[^"]*"',
        commit_replacement_line,
        r'__version__\s*=\s*"[^"]*"',
    )

    if update_date and current_date:
        content, _ = _replace_or_append(
            content,
            r'__date__\s*=\s*"[^"]*"',
            f'__date__ = "{current_date}"',
            r'__commit__\s*=\s*"[^"]*"',
        )

    version_file_path.write_text(content, encoding="utf-8")

    if stage:
        stage_version_file(version_file_path)

    if new_version != current_version:
        print(f"✓ Version updated: {current_version} -> {new_version}")
    elif not update_commit:
        print("✓ Version metadata refreshed")

    if update_commit and commit_value:
        print(f"   parent commit: {commit_value}")
    elif update_commit:
        print("   parent commit: unavailable")


def _load_shared_module() -> module:
    """Load shared git hook helpers."""
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "git_hooks" / "shared.py"

    spec = importlib.util.spec_from_file_location("krai_git_hook_shared", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - import failure path
        raise ImportError(f"Could not load shared module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(args: list[str] | None = None) -> int:
    """Run the updater manually for testing purposes."""

    shared = _load_shared_module()
    if shared.check_no_pycache_staged() != 0:
        return 1

    args = args if args is not None else sys.argv[1:]
    commit_message = args[0] if args else None

    version_file = Path("backend/processors/__version__.py")

    try:
        update_version_file(
            version_file,
            commit_message,
            update_commit=False,
        )
    except Exception as exc:  # pragma: no cover - defensive wrapper
        print(f"Warning: Error updating version file: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI behaviour
    sys.exit(main())
