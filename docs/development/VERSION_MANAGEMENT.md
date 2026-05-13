# 🔖 KRAI Version Management System

## Overview

The KRAI project uses an **automated version management system** that synchronizes version information and dates in `backend/processors/__version__.py` with every git commit, while CI synchronizes the commit hash after pushes.

### Key Features

- ✅ **Automatic Synchronization**: No manual updates needed
- ✅ **Locally Current**: Version and date stay in sync with git history; commit hash synchronized by CI shortly after push
- ✅ **Semantic Versioning**: Auto-increment based on commit message keywords
- ✅ **Cross-Platform**: Works on Windows, Linux, and macOS
- ✅ **Non-Blocking**: Never prevents commits from succeeding
- ✅ **CI/CD Ready**: Alternative workflow for teams

---

## How It Works

### Commit-msg Hook

A Python-based git hook runs automatically after you finish editing the commit message but before the commit is finalized:

1. **Reads** the pending commit message from the temporary file Git provides
2. **Parses** version keywords (MAJOR, MINOR, PATCH, …)
3. **Updates** the version number and date in `__version__.py`
4. **Stages** the updated file so it becomes part of the commit
5. **Lets the commit continue without blocking**

Because `commit-msg` executes before the new commit object exists, it does **not** rewrite `__commit__`. The existing value remains in place until CI updates it.

### Git Hook Execution Order

Git runs hooks in the following order: `pre-commit` → `prepare-commit-msg` → `commit-msg` → `post-commit`. KRAI only installs a `commit-msg` hook, ensuring the final commit message is available while still running before the commit is written.

### Version File

Located at `backend/processors/__version__.py`:

```python
__version__ = "2.1.3"  # Semantic Version (MAJOR.MINOR.PATCH)
__commit__ = "2e3dd89"  # Short Git Hash (7 characters) from CI
__date__ = "2025-10-29"  # ISO 8601 Date Format (YYYY-MM-DD)
```

**Commit hash semantics:**

> 💡 **Trade-off:** The local `commit-msg` hook updates `__version__` and `__date__` but leaves `__commit__` unchanged to avoid complications during the commit process. CI (`.github/workflows/version-sync.yml`) updates `__commit__` in a follow-up bot commit after push. This means `__commit__` may lag locally until you pull the CI sync commit.

- **Local commits:** The `commit-msg` hook updates the version and date only. `__commit__` keeps the previous value so the file stays stable during the commit.
- **CI updates:** `.github/workflows/version-sync.yml` runs after push and sets `__commit__` to the hash of the developer commit that triggered the workflow. The workflow creates a follow-up "sync" commit containing that hash, so the tracked value always reflects the latest real change.

### Git Integration

The hook receives the commit message file path from Git (passed as `argv[1]`) and reads it directly—no git command is used to retrieve the message. The hook uses the following git commands:
- `git add backend/processors/__version__.py` → Ensure the updated version file is staged
- `git rev-parse --short HEAD` (CI only) → Determine the current commit hash when running in GitHub Actions

### Semantic Versioning

Version increments are triggered by keywords in commit messages:

```
Developer commits → Hook runs → Parse message → Update version → Stage changes → Commit proceeds
```

---

## Installation

### Automatic Installation (Recommended)

Run the installation script from the project root:

```bash
python scripts/install_git_hooks.py
```

**Output:**
```
🔧 Installing Git hooks for version management...
✅ Hook installed successfully!
   Location: .git/hooks/commit-msg

📚 What happens now:
   • The commit-msg hook updates __version__.py using your commit message
   • The date is refreshed on every commit
   • Use keywords in commit messages to increment the semantic version
```

### Manual Installation

If you prefer manual installation:

```bash
# 1. Copy hook template to hooks directory
cp scripts/git_hooks/commit_msg.py .git/hooks/commit-msg

# 2. Make executable (Linux/Mac only)
chmod +x .git/hooks/commit-msg

# 3. Optional: create Windows wrapper
printf "@echo off\r\npy -3 \"%%~dp0\\commit-msg\" %%*\r\n" > .git/hooks/commit-msg.cmd

# 4. Test hook manually (using the current COMMIT_EDITMSG)
python .git/hooks/commit-msg .git/COMMIT_EDITMSG
```

### Verification

Check that the hook is installed correctly:

```bash
# Windows
dir .git\hooks\commit-msg*

# Linux/Mac
ls -la .git/hooks/commit-msg

# Test hook manually
python .git/hooks/commit-msg .git/COMMIT_EDITMSG
```

Expected output:
```
✓ Version metadata refreshed
```

---

## Usage

### Standard Commit (Date Update Only)

Regular commits update only the date (version unchanged unless keywords present; commit hash unchanged locally):

```bash
git commit -m "Fix: Logging issue in processor"
```

**Result:**
- `__version__` stays at `"2.1.3"` (no keyword)
- `__commit__` keeps its previous value locally (CI will update it after push)
- `__date__` updates to the current date

### Version Increment Commits

Use keywords in commit messages to increment the version:

#### Major Version (2.1.3 → 3.0.0)

Breaking changes or major releases:

```bash
git commit -m "RELEASE: Complete rewrite of processing pipeline"
git commit -m "MAJOR: Breaking API changes in database adapter"
```

**Keywords:** `RELEASE:`, `MAJOR:`

#### Minor Version (2.1.3 → 2.2.0)

New features or significant additions:

```bash
git commit -m "MINOR: Add video enrichment feature"
git commit -m "FEATURE: New database adapter pattern"
```

**Keywords:** `MINOR:`, `FEATURE:`

#### Patch Version (2.1.3 → 2.1.4)

Bug fixes or small improvements:

```bash
git commit -m "PATCH: Fix memory leak in embedding processor"
git commit -m "FIX: Correct chunk_id foreign key"
git commit -m "BUGFIX: Handle empty PDF pages"
```

**Keywords:** `PATCH:`, `FIX:`, `BUGFIX:`

### Keywords Reference

| Keyword | Version Change | Example |
|---------|---------------|---------|
| `RELEASE:` | Major (X.0.0) | 2.1.3 → 3.0.0 |
| `MAJOR:` | Major (X.0.0) | 2.1.3 → 3.0.0 |
| `MINOR:` | Minor (X.Y.0) | 2.1.3 → 2.2.0 |
| `FEATURE:` | Minor (X.Y.0) | 2.1.3 → 2.2.0 |
| `PATCH:` | Patch (X.Y.Z) | 2.1.3 → 2.1.4 |
| `FIX:` | Patch (X.Y.Z) | 2.1.3 → 2.1.4 |
| `BUGFIX:` | Patch (X.Y.Z) | 2.1.3 → 2.1.4 |
| *(none)* | No change | 2.1.3 → 2.1.3 |

**Note:** Keywords are **case-insensitive** (`fix:`, `FIX:`, `Fix:` all work).

---

## Version File Format

### Structure

The `__version__.py` file contains:

```python
"""Version information for KRAI processors."""

__version__ = "2.1.3"  # Semantic Version
__commit__ = "2e3dd89"  # Short Git Hash
__date__ = "2025-10-29"  # ISO Date Format

# Version History:
# 2.1.3 (2e3dd89) - Added automatic version management
# 2.1.2 (a1b2c3d) - Fixed embedding processor
# 2.1.1 (x9y8z7w) - Improved chunk linking
```

### Fields

- **`__version__`**: Semantic Versioning format (MAJOR.MINOR.PATCH)
- **`__commit__`**: Short Git hash (7 characters)
- **`__date__`**: ISO 8601 date format (YYYY-MM-DD)

### Version History

The version history section is **NOT automatically updated**. Add entries manually for important releases:

```python
# Version History:
# X.Y.Z (hash) - Brief description of changes
```

---

## Troubleshooting

### Hook Not Executing

**Symptom:** Version file doesn't update after commits.

**Solutions:**

```bash
# Check if hook exists
ls -la .git/hooks/commit-msg      # Linux/Mac
dir .git\hooks\commit-msg*       # Windows

# Check permissions (Linux/Mac)
chmod +x .git/hooks/commit-msg

# Test hook manually
python .git/hooks/commit-msg .git/COMMIT_EDITMSG

# Re-install hook
python scripts/install_git_hooks.py
```

### Version Not Updating

**Symptom:** Date updates but version stays the same.

**Cause:** No keyword in commit message (this is expected behavior).

**Solution:** Use version keywords (`MAJOR:`, `MINOR:`, `PATCH:`) in commit message.

### Hook Blocking Commits

**Symptom:** Commits fail with hook error.

**Note:** The hook is designed to **NEVER block commits** (always exits with code 0).

**If this happens:**

1. Check hook code for `sys.exit(1)` calls
2. Temporarily bypass hook: `git commit --no-verify`
3. Report issue to development team

### Windows-Specific Issues

**Python Not Found:**

```bash
# Ensure Python is in PATH
python --version

# If not found, add Python to PATH or use full path in the hook
```

**Shebang Not Working / CMD wrapper missing:**

- Re-run `python scripts/install_git_hooks.py` to regenerate `.git/hooks/commit-msg.cmd`.
- Confirm the wrapper contains `py -3 "%~dp0\commit-msg" %*` and that `py` is callable.

**Fallback:** Run the hook manually before committing:

```bash
python .git/hooks/commit-msg .git/COMMIT_EDITMSG
git commit --amend --no-edit
```

### Version File Not Found

**Symptom:** Hook warns "Version file not found".

**Solution:**

```bash
# Check if file exists
ls backend/processors/__version__.py

# If missing, create it manually or restore from git
git checkout backend/processors/__version__.py
```

---

## CI/CD Alternative

For teams that prefer not to use git hooks, a **GitHub Actions workflow** is available as an alternative.

### GitHub Actions Workflow

The workflow automatically updates the version file after pushes to `master` or `main`:

**File:** `.github/workflows/version-sync.yml`

```yaml
name: Version Sync

on:
  push:
    branches: [master, main]
    paths-ignore:
      - 'backend/processors/__version__.py'

jobs:
  sync-version:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Update Version
        run: python scripts/update_version_ci.py
      - name: Commit Changes
        run: |
          git config user.name "GitHub Actions Bot"
          git config user.email "actions@github.com"
          git add backend/processors/__version__.py
          git commit -m "chore: Auto-update version [skip ci]" || true
          git push
```

### Advantages of CI/CD

- ✅ Centrally managed (no local installation)
- ✅ Works for all team members automatically
- ✅ No client-side setup required

### Disadvantages of CI/CD

- ❌ Delayed (only runs after push)
- ❌ Creates extra commit in history
- ❌ More complex setup

### Recommendation

**Use git hooks for local development** + **CI/CD as backup** for team members who don't install hooks. CI will always normalize `__commit__` even if contributors skip the local hook.

---

## Best Practices

### Commit Message Conventions

**Consistency:**
- Always use the same keywords (`MAJOR:`, `MINOR:`, `PATCH:`)
- Place keyword at the start of the message
- Use descriptive messages after the keyword

**Examples:**

```bash
# Good
git commit -m "MINOR: Add OEM manufacturer search integration"
git commit -m "FIX: Resolve memory leak in embedding processor"

# Avoid
git commit -m "Added feature (minor)"  # Keyword not recognized
git commit -m "fix bug"  # Too vague
```

### Version History Maintenance

**When to Update:**
- Add entries for **MAJOR** and **MINOR** releases
- Include brief description of changes
- Keep format consistent

**Format:**

```python
# Version History:
# X.Y.Z (hash) - Brief description
```

**Example:**

```python
# Version History:
# 3.0.0 (abc1234) - Complete rewrite with new architecture
# 2.2.0 (def5678) - Added video enrichment and OEM search
# 2.1.4 (ghi9012) - Fixed memory leaks and improved performance
```

### Team Workflow

**Onboarding New Developers:**

1. Include hook installation in setup documentation
2. Add to `SETUP_NEW_COMPUTER.md`
3. Run `python scripts/install_git_hooks.py` during setup

**Updating Hooks:**

When hook logic changes:

```bash
# Re-run installation to update
python scripts/install_git_hooks.py
```

**Documentation:**
- Reference this guide in project README
- Include in developer onboarding
- Keep examples up to date
- Reinforce that `__commit__` comes from CI to avoid confusion

### Merge Conflict Awareness

`backend/processors/__version__.py` changes on almost every commit, so long-lived feature branches can accumulate merge conflicts. Recommended practices:

1. Rebase frequently against `main`/`master` to replay the latest version file updates.
2. Resolve conflicts by keeping the higher semantic version and latest CI-generated commit hash.
3. Consider adding a branch-specific strategy (e.g., `.gitattributes` using `ours`) if your workflow suffers from frequent conflicts.

---

## Technical Details

### Hook Implementation

**Language:** Python 3.7+ (cross-platform compatibility)

**Dependencies:** Standard library only
- `subprocess` - Git command execution
- `pathlib` - File path handling
- `datetime` - Date formatting
- `re` - Regex for version parsing
- `sys` - Exit codes

**Execution Time:** < 100ms (imperceptible to user)

**Error Handling:** Graceful degradation
- Warnings instead of errors
- Always exits with code 0
- Never blocks commits

### Version Parsing

**Regex Pattern:**

```python
__version__\s*=\s*"([^"]+)"
```

**Format:** Semantic Versioning (MAJOR.MINOR.PATCH)

**Validation:** Checks for valid version format before incrementing

### Git Commands

The hook uses these git commands:

```bash
# Stage updated version file
git add backend/processors/__version__.py

# Get short commit hash (7 characters) - CI only
git rev-parse --short HEAD
```

**Note:** The `commit-msg` hook receives the message file path from Git and reads it directly; no git command is used to retrieve the commit message locally.

### File Operations

**Read:** UTF-8 encoding for cross-platform compatibility

**Write:** Preserves original file encoding and line endings

**Atomic:** Uses regex replacement to avoid corrupting file structure

---

## FAQ

**Q: Can I disable the hook?**

A: Yes, in two ways:
1. Delete `.git/hooks/commit-msg` (and `.git/hooks/commit-msg.cmd` on Windows)
2. Use `git commit --no-verify` to bypass for a single commit

**Q: What happens with merge commits?**

A: The hook runs normally and uses the merge commit message. If the merge message contains keywords, the version will increment.

**Q: Does this work with Git GUI tools?**

A: Yes! All Git clients (GitHub Desktop, GitKraken, SourceTree, etc.) execute hooks automatically.

**Q: Can I manually change the version?**

A: Yes! Edit `__version__.py` directly. The hook will only update it on the next commit.

**Q: What about branches?**

A: The hook runs on all branches. Each branch maintains its own version in `__version__.py`.

**Q: How do I test the hook without committing?**

A: Run the test suite:

```bash
python scripts/test_version_hook.py
```

**Q: What if I forget to use keywords?**

A: No problem! The version stays the same; the date updates locally, and CI will update the commit hash after push. You can manually edit the version later if needed.

**Q: Can I use multiple keywords in one commit?**

A: The hook uses the first matching keyword (in order: MAJOR → MINOR → PATCH).

---

## Summary

### What's Automated

- ✅ Commit hash updated by CI after push (may lag locally until the CI sync commit)
- ✅ Date update on every commit
- ✅ Version increment with keyword commits

### What's Manual

- ❌ Version history entries
- ❌ Release notes
- ❌ Changelog updates

### Recommended Workflow

1. **Install hook:** `python scripts/install_git_hooks.py`
2. **Normal commits:** Version stays the same (date updates locally; commit hash updates in CI after push)
3. **Release commits:** Use keywords (`MAJOR:`, `MINOR:`, `PATCH:`)
4. **Important releases:** Update version history manually

### Quick Reference

```bash
# Install hook
python scripts/install_git_hooks.py

# Test hook
python scripts/test_version_hook.py

# Normal commit (no version change)
git commit -m "Fix: Bug in processor"

# Version increment commit
git commit -m "MINOR: Add new feature"

# Bypass hook (if needed)
git commit --no-verify -m "Emergency fix"
```

---

**Last Updated:** 2025-10-29
**Version:** 1.0
**Author:** KRAI Development Team
**Maintainer:** See `scripts/install_git_hooks.py` for contact
