#!/usr/bin/env python3
"""Validate the consolidated `.env` configuration for the KRAI Engine.

This script ensures that all required environment variables are present and
conform to expected formats before starting Docker services.

Usage:
    python scripts/validate_env.py
    python scripts/validate_env.py --verbose
    python scripts/validate_env.py --env-file path/to/.env
    python scripts/validate_env.py --strict

Exit codes:
    0 -> Validation succeeded with no warnings.
    1 -> Validation succeeded with warnings (non-strict mode).
    2 -> Validation failed due to errors, or warnings in strict mode.
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

try:  # pragma: no cover - optional dependency
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:  # pragma: no cover - graceful degradation
    Console = None  # type: ignore
    Table = None  # type: ignore
    Panel = None  # type: ignore
    Text = None  # type: ignore
    box = None  # type: ignore


def requires_firecrawl_api_key(env: dict[str, str]) -> bool:
    """Determine whether the Firecrawl API key must be present."""

    flag = env.get("FIRECRAWL_REQUIRE_API_KEY")
    if flag and flag.strip().lower() in {"1", "true", "yes", "on"}:
        return True

    api_url = env.get("FIRECRAWL_API_URL", "").strip()
    if not api_url:
        return False

    try:
        parsed = urlparse(api_url)
    except Exception:
        return False

    host = (parsed.hostname or "").lower()
    if not host:
        return False

    local_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "krai-firecrawl"}
    if host in local_hosts or host.endswith(".local") or host.endswith(".internal"):
        return False

    return True


REQUIRED_VARIABLES: dict[str, dict[str, object]] = {
    "DATABASE_PASSWORD": {
        "type": "password",
        "min_length": 12,
        "description": "Password for the PostgreSQL superuser",
    },
    "OBJECT_STORAGE_SECRET_KEY": {
        "type": "password",
        "min_length": 12,
        "description": "Secret key for MinIO / object storage access",
    },
    "JWT_PRIVATE_KEY": {
        "type": "base64",
        "min_length": 100,
        "description": "Base64 encoded RSA private key (2048-bit)",
    },
    "JWT_PUBLIC_KEY": {
        "type": "base64",
        "min_length": 100,
        "description": "Base64 encoded RSA public key (2048-bit)",
    },
    "DEFAULT_ADMIN_PASSWORD": {
        "type": "password",
        "min_length": 12,
        "description": "Initial administrator password for dashboard access",
    },
    "OLLAMA_URL": {
        "type": "url",
        "pattern": r"^https?://",
        "description": "Base URL for the Ollama service",
    },
}

OPTIONAL_VARIABLES: dict[str, dict[str, str]] = {
    "YOUTUBE_API_KEY": {
        "description": "YouTube Data API key (optional - analytics & ingestion)",
        "source": "https://console.cloud.google.com/apis/credentials",
    },
    "CLOUDFLARE_TUNNEL_TOKEN": {
        "description": "Cloudflare Tunnel token for remote agents",
        "source": "https://dash.cloudflare.com/",
    },
    "OPENAI_API_KEY": {
        "description": "OpenAI API key (required when FIRECRAWL_LLM_PROVIDER=openai)",
        "source": "https://platform.openai.com/account/api-keys",
    },
}

CONDITIONAL_VARIABLES: list[dict[str, object]] = [
    {
        "when": {"SCRAPING_BACKEND": "firecrawl"},
        "variables": {
            "FIRECRAWL_API_URL": {
                "type": "url",
                "pattern": r"^https?://",
                "description": "Base URL for the Firecrawl API service",
            },
            "FIRECRAWL_BULL_AUTH_KEY": {
                "type": "password",
                "min_length": 12,
                "description": "Authentication key for Firecrawl Bull queue",
            },
        },
    },
    {
        "predicate": requires_firecrawl_api_key,
        "variables": {
            "FIRECRAWL_API_KEY": {
                "type": "password",
                "min_length": 12,
                "description": "Firecrawl API key for external access",
            }
        },
    },
]

DOCKER_SERVICE_NAMES: dict[str, str] = {
    "DATABASE_HOST": "krai-postgres",
    "OBJECT_STORAGE_ENDPOINT": "http://krai-minio:9000",
    "OLLAMA_URL": "http://krai-ollama:11434",
}

PASSWORD_COMPLEXITY_RULES: dict[str, str] = {
    "uppercase": r"[A-Z]",
    "lowercase": r"[a-z]",
    "digit": r"\d",
    "special": r"[^\w\s]",
}

ENV_FILE_NAMES: tuple[str, ...] = (".env", ".env.local", ".env.database")


@dataclass
class ValidationMessage:
    """Represents an individual validation outcome."""

    level: str
    variable: str
    message: str


class EnvValidator:
    """Encapsulates validation logic for the consolidated `.env` file."""

    def __init__(
        self,
        env_path: Path,
        verbose: bool = False,
        strict: bool = False,
        enforce_complexity: bool = True,
        docker_context: bool | None = None,
    ) -> None:
        self.env_path = env_path
        self.verbose = verbose
        self.strict = strict
        self.enforce_complexity = enforce_complexity
        self.docker_context: bool | None = docker_context
        self.console: Console | None = Console() if Console else None
        self.env_vars: dict[str, str] = {}
        self.errors: list[ValidationMessage] = []
        self.warnings: list[ValidationMessage] = []
        self.infos: list[ValidationMessage] = []

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def run_validation(self) -> bool:
        """Execute all validation steps in sequence."""

        if not self.load_env_file():
            return False

        password_policies = self._load_password_policies()

        if self.docker_context is None:
            self.docker_context = self._infer_docker_context()

        self.validate_required_variables(REQUIRED_VARIABLES, password_policies)
        self.validate_optional_variables(OPTIONAL_VARIABLES)
        self.validate_conditional_variables(CONDITIONAL_VARIABLES, password_policies)

        if self.docker_context:
            self.validate_docker_service_names(DOCKER_SERVICE_NAMES)

        return not self.errors and (not self.strict or not self.warnings)

    def print_results(self) -> None:
        """Render validation output using rich if available, else plain text."""

        if self.console:
            self._print_results_rich()
        else:
            self._print_results_plain()

    def summary_exit_code(self) -> int:
        """Derive exit code based on collected errors and warnings."""

        if self.errors:
            return 2
        if self.warnings and self.strict:
            return 2
        if self.warnings:
            return 1
        return 0

    # ------------------------------------------------------------------
    # Validation steps
    # ------------------------------------------------------------------
    def load_env_file(self) -> bool:
        """Load key/value pairs from the specified .env file."""

        if not self.env_path.exists():
            self.errors.append(ValidationMessage("error", "FILE", f"Environment file not found: {self.env_path}"))
            return False

        for line_no, line in enumerate(self.env_path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                self.warnings.append(
                    ValidationMessage(
                        "warning",
                        f"LINE {line_no}",
                        "Ignoring malformed line (missing '=')",
                    )
                )
                continue

            key, value = stripped.split("=", 1)
            key = key.strip()
            value = self._strip_quotes(value.strip())

            if key:
                self.env_vars[key] = value

        if self.verbose:
            self.infos.append(
                ValidationMessage(
                    "info",
                    "FILE",
                    f"Loaded {len(self.env_vars)} variables from {self.env_path}",
                )
            )

        return True

    def validate_required_variables(
        self,
        requirements: dict[str, dict[str, object]],
        password_policies: dict[str, object] | None = None,
    ) -> None:
        """Ensure required variables are present and valid."""

        for variable, rules in requirements.items():
            value = self.env_vars.get(variable, "").strip()
            if not value:
                self.errors.append(ValidationMessage("error", variable, "Missing required variable"))
                continue

            min_length = int(rules.get("min_length", 0))
            if min_length and len(value) < min_length:
                self.errors.append(
                    ValidationMessage(
                        "error",
                        variable,
                        f"Value must be at least {min_length} characters (found {len(value)})",
                    )
                )
                continue

            value_type = str(rules.get("type", "")).lower()
            pattern = str(rules.get("pattern", ""))

            if pattern and not re.match(pattern, value):
                self.errors.append(
                    ValidationMessage(
                        "error",
                        variable,
                        "Value does not match required format",
                    )
                )
                continue

            if value_type == "password" and not self.validate_password_complexity(value, min_length, password_policies):
                self.errors.append(
                    ValidationMessage(
                        "error",
                        variable,
                        "Password does not meet complexity requirements",
                    )
                )
            elif value_type == "base64" and not self.validate_base64(value):
                self.errors.append(ValidationMessage("error", variable, "Value is not valid base64"))
            elif value_type == "url" and not self.validate_url(value):
                self.errors.append(ValidationMessage("error", variable, "Value is not a valid URL"))

    def validate_optional_variables(self, optional_vars: dict[str, dict[str, str]]) -> None:
        """Emit warnings for optional variables that are missing or empty."""

        for variable, meta in optional_vars.items():
            value = self.env_vars.get(variable, "").strip()
            if not value:
                source = meta.get("source", "Documentation")
                description = meta.get("description", "Optional variable")
                self.warnings.append(
                    ValidationMessage(
                        "warning",
                        variable,
                        f"Optional variable not set - {description}. Source: {source}",
                    )
                )

    def validate_conditional_variables(
        self,
        conditional_rules: list[dict[str, object]],
        password_policies: dict[str, object] | None = None,
    ) -> None:
        """Validate variables that depend on other configuration values."""

        for rule in conditional_rules:
            should_apply = True

            predicate = rule.get("predicate")
            if callable(predicate):
                try:
                    should_apply = bool(predicate(self.env_vars))
                except Exception as exc:
                    should_apply = False
                    self.warnings.append(
                        ValidationMessage(
                            "warning",
                            "CONDITIONAL",
                            f"Failed to evaluate predicate: {exc}",
                        )
                    )

            if should_apply:
                conditions = rule.get("when")
                if conditions:
                    should_apply = self._conditions_satisfied(conditions)

            if not should_apply:
                continue

            variables = rule.get("variables", {})
            if not isinstance(variables, dict):
                continue

            self.validate_required_variables(variables, password_policies)  # type: ignore[arg-type]

    def validate_docker_service_names(self, expected: dict[str, str]) -> None:
        """Warn when Docker-specific variables use non-container hostnames."""

        for variable, expected_value in expected.items():
            actual = self.env_vars.get(variable)
            if not actual:
                continue

            if actual.strip() != expected_value:
                self.warnings.append(
                    ValidationMessage(
                        "warning",
                        variable,
                        ("Expected Docker service reference " f"`{expected_value}` but found `{actual}`."),
                    )
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def validate_password_complexity(
        self, password: str, min_length: int, password_policies: dict[str, object] | None
    ) -> bool:
        """Check that a password meets minimum complexity requirements."""

        policies = password_policies or {}
        require_upper = bool(policies.get("require_upper", False))
        require_lower = bool(policies.get("require_lower", False))
        require_digit = bool(policies.get("require_number", False))
        require_special = bool(policies.get("require_special", False))
        min_length_override = int(policies.get("min_length", min_length or 0))

        effective_min_length = max(min_length_override, min_length or 0)

        if len(password) < max(effective_min_length, 1):
            return False

        if not self.enforce_complexity:
            return True

        required_rules = []
        if require_upper:
            required_rules.append("uppercase")
        if require_lower:
            required_rules.append("lowercase")
        if require_digit:
            required_rules.append("digit")
        if require_special:
            required_rules.append("special")

        for rule_name in required_rules:
            pattern = PASSWORD_COMPLEXITY_RULES[rule_name]
            if not re.search(pattern, password):
                if self.verbose:
                    self.infos.append(
                        ValidationMessage(
                            "info",
                            "COMPLEXITY",
                            f"Password missing required character class: {rule_name}",
                        )
                    )
                return False
        return True

    def _load_password_policies(self) -> dict[str, object]:
        policies: dict[str, object] = {}
        min_length_env = self.env_vars.get("PASSWORD_MIN_LENGTH")
        if min_length_env and min_length_env.isdigit():
            policies["min_length"] = int(min_length_env)
        policies["require_upper"] = self._flag_enabled("PASSWORD_REQUIRE_UPPERCASE")
        policies["require_lower"] = self._flag_enabled("PASSWORD_REQUIRE_LOWERCASE")
        policies["require_number"] = self._flag_enabled("PASSWORD_REQUIRE_NUMBER")
        policies["require_special"] = self._flag_enabled("PASSWORD_REQUIRE_SPECIAL")
        return policies

    def _flag_enabled(self, key: str) -> bool:
        value = self.env_vars.get(key)
        if value is None:
            return False
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _infer_docker_context(self) -> bool:
        compose_project = self.env_vars.get("COMPOSE_PROJECT_NAME")
        if compose_project:
            return True

        env_designation = self.env_vars.get("ENV") or self.env_vars.get("ENVIRONMENT")
        if env_designation and env_designation.strip().lower() in {"production", "staging"}:
            return True

        return False

    @staticmethod
    def validate_base64(value: str) -> bool:
        """Return True if a string is valid base64."""

        try:
            base64.b64decode(value, validate=True)
            return True
        except Exception:
            return False

    @staticmethod
    def validate_url(value: str) -> bool:
        """Simple URL validation supporting HTTP/HTTPS."""

        url_pattern = re.compile(r"^https?://[^\s]+$")
        return bool(url_pattern.match(value))

    @staticmethod
    def _strip_quotes(value: str) -> str:
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            return value[1:-1]
        return value

    def _conditions_satisfied(self, conditions: dict[str, str]) -> bool:
        for key, expected_value in conditions.items():
            actual_value = self.env_vars.get(key)
            if actual_value is None:
                return False
            if actual_value.strip().lower() != str(expected_value).strip().lower():
                return False
        return True

    # ------------------------------------------------------------------
    # Output rendering
    # ------------------------------------------------------------------
    def _print_results_plain(self) -> None:
        print(f"🔍 Validating environment file: {self.env_path}\n")

        if self.infos and self.verbose:
            for message in self.infos:
                print(f"ℹ️  {message.variable}: {message.message}")
            if self.verbose:
                print()

        for collection, emoji in ((self.errors, "❌"), (self.warnings, "⚠️")):
            if not collection:
                continue
            for message in collection:
                print(f"{emoji}  {message.variable}: {message.message}")
            print()

        if not self.errors and not self.warnings:
            print("✅ Validation passed with no issues detected.\n")
        elif not self.errors:
            print("⚠️  Validation completed with warnings.\n")
        else:
            print("❌ Validation failed. See details above.\n")

    def _print_results_rich(self) -> None:
        assert self.console  # narrow type

        header = Text.assemble(("🔍 Validating environment file ", "bold"), str(self.env_path))
        self.console.rule(header)

        if self.infos and self.verbose:
            info_table = Table(box=box.MINIMAL_DOUBLE_HEAD, show_header=True, title="Details")
            info_table.add_column("Type", style="cyan", no_wrap=True)
            info_table.add_column("Target", style="magenta", no_wrap=True)
            info_table.add_column("Message", style="white")
            for message in self.infos:
                info_table.add_row("info", message.variable, message.message)
            self.console.print(info_table)

        if self.errors:
            error_table = self._build_table("Errors", "red")
            for message in self.errors:
                error_table.add_row("ERROR", message.variable, message.message)
            self.console.print(error_table)

        if self.warnings:
            warning_table = self._build_table("Warnings", "yellow")
            for message in self.warnings:
                warning_table.add_row("WARNING", message.variable, message.message)
            self.console.print(warning_table)

        if not self.errors and not self.warnings:
            panel = Panel("✅ Validation passed with no issues detected.", style="green")
        elif not self.errors and self.warnings:
            panel = Panel(
                "⚠️  Validation completed with warnings. Review optional configuration.",
                style="yellow",
            )
        else:
            panel = Panel("❌ Validation failed. See details above.", style="red")

        self.console.print(panel)
        self.console.rule()

    def _build_table(self, title: str, color: str) -> Table:
        assert self.console
        table = Table(box=box.SIMPLE_HEAVY)
        table.title = title
        table.add_column("Level", style=color, no_wrap=True)
        table.add_column("Variable", style="magenta", no_wrap=True)
        table.add_column("Message", style="white")
        return table


# ----------------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------------


def find_env_file(target: str | None) -> Path:
    """Locate the environment file to validate."""

    if target:
        return Path(target).expanduser().resolve()

    current = Path.cwd()
    for parent in [current, *current.parents]:
        for candidate in ENV_FILE_NAMES:
            candidate_path = parent / candidate
            if candidate_path.exists():
                return candidate_path

    # Default to project root `.env` even if missing (error recorded later)
    return current / ENV_FILE_NAMES[0]


def print_validation_summary(errors: Iterable[ValidationMessage], warnings: Iterable[ValidationMessage]) -> None:
    """Print a succinct summary using plain text fallback."""

    error_count = sum(1 for _ in errors)
    warning_count = sum(1 for _ in warnings)

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Summary: {error_count} errors, {warning_count} warnings")
    if error_count:
        print("❌ Fix errors before starting Docker services.")
    elif warning_count:
        print("⚠️  Review optional configuration to unlock full functionality.")
    else:
        print("✅ Environment is ready for Docker startup.")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")


# ----------------------------------------------------------------------
# CLI entry point
# ----------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the consolidated .env file.")
    parser.add_argument(
        "--env-file",
        dest="env_file",
        help="Path to the .env file (defaults to nearest .env in directory tree)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed diagnostic output",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )
    parser.add_argument(
        "--no-complexity",
        action="store_true",
        help="Skip password complexity checks (min length still enforced)",
    )
    parser.add_argument(
        "--docker-context",
        dest="docker_context",
        choices=["auto", "on", "off"],
        default="auto",
        help="Control Docker-specific warnings: auto (default), on, or off",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    env_path = find_env_file(args.env_file)

    docker_context: bool | None
    if args.docker_context == "on":
        docker_context = True
    elif args.docker_context == "off":
        docker_context = False
    else:
        docker_context = None

    validator = EnvValidator(
        env_path=env_path,
        verbose=args.verbose,
        strict=args.strict,
        enforce_complexity=not args.no_complexity,
        docker_context=docker_context,
    )
    validator.run_validation()
    validator.print_results()

    if not validator.console:
        print_validation_summary(validator.errors, validator.warnings)

    return validator.summary_exit_code()


if __name__ == "__main__":
    sys.exit(main())
