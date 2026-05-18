#!/usr/bin/env python3
"""Installation script for Git hooks used in version management."""

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

HOOK_SPECS = [
    {
        "name": "commit-msg",
        "template": "commit_msg.py",
    },
    {
        "name": "pre-commit",
        "template": "pre_commit.py",
    },
]


def install_hooks():
    """Install Git hooks for automatic version management."""

    project_root = Path(__file__).parent.parent
    hooks_dir = project_root / ".git" / "hooks"

    print("Installing Git hooks for version management...")
    print(f"   Project root: {project_root}")

    # Validate git repository
    git_dir = project_root / ".git"
    if not git_dir.exists():
        print("Error: Not a git repository!")
        print(f"   Could not find .git directory at: {git_dir}")
        sys.exit(1)

    # Validate hook templates exist
    for hook_spec in HOOK_SPECS:
        hook_template = project_root / "scripts" / "git_hooks" / hook_spec["template"]
        if not hook_template.exists():
            print("Error: Hook template not found!")
            print(f"   Expected at: {hook_template}")
            sys.exit(1)

    # Create hooks directory if it doesn't exist
    hooks_dir.mkdir(parents=True, exist_ok=True)

    for hook_spec in HOOK_SPECS:
        hook_name = hook_spec["name"]
        hook_source = hooks_dir / hook_name
        hook_template = project_root / "scripts" / "git_hooks" / hook_spec["template"]

        # Backup existing hook if present
        if hook_source.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = hook_source.parent / f"{hook_name}.backup.{timestamp}"
            print(f"Backing up existing {hook_name} hook to: {backup_path.name}")
            shutil.copy2(hook_source, backup_path)

        # Copy hook template to hooks directory
        print(f"Copying {hook_name} hook template...")
        shutil.copy2(hook_template, hook_source)

        # Make hook executable on Unix systems
        if sys.platform != "win32":
            print(f"Making {hook_name} hook executable...")
            os.chmod(hook_source, 0o755)
        else:
            wrapper_path = hook_source.with_suffix(".cmd")
            print(f"Writing Windows wrapper: {wrapper_path.name}")
            wrapper_content = "@echo off\r\n" f'py -3 "%~dp0\\{hook_name}" %*\r\n'
            wrapper_path.write_text(wrapper_content, encoding="utf-8")

    # Verify installation
    installed_hooks = [hooks_dir / hook_spec["name"] for hook_spec in HOOK_SPECS]
    if all(hook.exists() for hook in installed_hooks):
        print("Hooks installed successfully!")
        for hook in installed_hooks:
            print(f"   Location: {hook}")
        print()
        print("What happens now:")
        print("   - The pre-commit hook blocks staged __pycache__/*.pyc artifacts")
        print("   - The commit-msg hook updates __version__.py using your commit message")
        print("   - Commit hash and date are always updated")
        print("   - Use keywords in commit messages to increment version:")
        print("     - 'RELEASE:' or 'MAJOR:' -> Increment major version (2.1.3 -> 3.0.0)")
        print("     - 'MINOR:' or 'FEATURE:' -> Increment minor version (2.1.3 -> 2.2.0)")
        print("     - 'PATCH:' or 'FIX:' or 'BUGFIX:' -> Increment patch version (2.1.3 -> 2.1.4)")
        print()
        print("For more details, see: docs/development/VERSION_MANAGEMENT.md")
    else:
        print("Error: Hook installation failed!")
        sys.exit(1)


def main():
    """Main entry point."""
    try:
        install_hooks()
    except Exception as e:
        print(f"Error during hook installation: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
