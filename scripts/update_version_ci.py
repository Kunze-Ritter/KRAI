#!/usr/bin/env python3
"""
CI/CD version update script.
Alternative to Git hooks for GitHub Actions, GitLab CI, and other CI/CD systems.
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


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


def get_git_info_ci():
    """
    Get git commit hash and message from CI environment or git commands.

    Supports:
    - GitHub Actions (GITHUB_SHA, GITHUB_REF)
    - GitLab CI (CI_COMMIT_SHA, CI_COMMIT_MESSAGE)
    - Generic fallback (git commands)
    """
    commit_hash = None
    commit_message = None

    # Try GitHub Actions environment variables
    if "GITHUB_SHA" in os.environ:
        commit_hash = os.environ["GITHUB_SHA"][:7]  # Short hash
        try:
            commit_message = subprocess.check_output(
                ["git", "log", "-1", "--pretty=%B"], stderr=subprocess.STDOUT, text=True
            ).strip()
        except subprocess.CalledProcessError:
            pass

    # Try GitLab CI environment variables
    elif "CI_COMMIT_SHA" in os.environ:
        commit_hash = os.environ["CI_COMMIT_SHA"][:7]  # Short hash
        commit_message = os.environ.get("CI_COMMIT_MESSAGE", "")

    # Fallback to git commands
    if not commit_hash:
        try:
            commit_hash = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.STDOUT, text=True
            ).strip()

            commit_message = subprocess.check_output(
                ["git", "log", "-1", "--pretty=%B"], stderr=subprocess.STDOUT, text=True
            ).strip()
        except subprocess.CalledProcessError as e:
            print(f"Error: Could not get git info: {e}", file=sys.stderr)
            return None, None

    return commit_hash, commit_message


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


def update_version_file_ci(version_file_path, dry_run=False, verbose=False):
    """
    Update the version file with current git info and optionally increment version.

    Args:
        version_file_path: Path to __version__.py
        dry_run: If True, don't write changes
        verbose: If True, print detailed information

    Returns:
        bool: True if update was performed, False if already up to date
    """
    if not version_file_path.exists():
        print(f"Error: Version file not found: {version_file_path}", file=sys.stderr)
        return False

    # Read current version file
    content = version_file_path.read_text(encoding="utf-8")

    # Extract current version
    version_match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    if not version_match:
        print("Error: Could not find __version__ in version file", file=sys.stderr)
        return False

    current_version = version_match.group(1)

    # Extract current commit hash
    commit_match = re.search(r'__commit__\s*=\s*"([^"]*)"', content)
    current_commit = commit_match.group(1) if commit_match else ""

    # Get git info
    commit_hash, commit_message = get_git_info_ci()
    if not commit_hash:
        print("Error: Could not get git info", file=sys.stderr)
        return False

    # Check if already up to date
    if current_commit == commit_hash:
        if verbose:
            print(f"Already up to date (commit: {commit_hash})")
        return False

    # Calculate new version
    new_version = increment_version(current_version, commit_message)

    # Get current date
    current_date = datetime.now().strftime("%Y-%m-%d")

    if verbose:
        print(f"Current version: {current_version}")
        print(f"New version: {new_version}")
        print(f"Commit: {commit_hash}")
        print(f"Date: {current_date}")
        print(f"Message: {commit_message[:50]}...")

    if dry_run:
        print("Dry run mode - no changes written")
        return True

    # Update content and insert missing fields
    new_content, _ = _replace_or_append(
        content,
        r'__version__\s*=\s*"[^"]*"',
        f'__version__ = "{new_version}"',
        r'__version__\s*=\s*"[^"]*"',
    )
    new_content, _ = _replace_or_append(
        new_content,
        r'__commit__\s*=\s*"[^"]*"',
        f'__commit__ = "{commit_hash}"',
        r'__version__\s*=\s*"[^"]*"',
    )
    new_content, _ = _replace_or_append(
        new_content,
        r'__date__\s*=\s*"[^"]*"',
        f'__date__ = "{current_date}"',
        r'__commit__\s*=\s*"[^"]*"',
    )

    # Write updated content
    version_file_path.write_text(new_content, encoding="utf-8")

    if new_version != current_version:
        print(f"✓ Version updated: {current_version} -> {new_version} (commit: {commit_hash})")
    else:
        print(f"✓ Version file updated with commit: {commit_hash}")

    return True


def main():
    """Main entry point for CI/CD version update."""
    parser = argparse.ArgumentParser(description="Update version file in CI/CD environment")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes")
    parser.add_argument("--verbose", action="store_true", help="Print detailed information")
    parser.add_argument(
        "--version-file",
        type=str,
        default="backend/processors/__version__.py",
        help="Path to version file (default: backend/processors/__version__.py)",
    )

    args = parser.parse_args()

    # Define version file path
    VERSION_FILE = Path(args.version_file)

    if not VERSION_FILE.exists():
        print(f"Error: Version file not found: {VERSION_FILE}", file=sys.stderr)
        sys.exit(1)

    try:
        updated = update_version_file_ci(VERSION_FILE, dry_run=args.dry_run, verbose=args.verbose)

        if updated:
            sys.exit(0)  # Success
        else:
            sys.exit(0)  # Already up to date (not an error)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
