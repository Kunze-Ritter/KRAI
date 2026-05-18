#!/usr/bin/env python3
"""
Admin User Creation Script

This script creates an admin user with all necessary permissions.
Run this script after setting up the database and before starting the application.
"""

import argparse
import asyncio
import os
import sys
from getpass import getpass
from pathlib import Path

# Add project root and backend directory to sys.path before internal imports
project_root = Path(__file__).parent.parent.parent
backend_dir = project_root / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_dir))

from processors.env_loader import load_all_env_files


def _load_env_files() -> None:
    """Load environment configuration required for admin creation."""
    load_all_env_files(project_root)


_load_env_files()

# Import after environment loading and path setup
from api.dependencies.auth_factory import create_auth_service
from services.auth_service import AuthenticationError, AuthService

# Default admin user details
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com")
DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_FIRST_NAME = os.getenv("DEFAULT_ADMIN_FIRST_NAME", "System")
DEFAULT_ADMIN_LAST_NAME = os.getenv("DEFAULT_ADMIN_LAST_NAME", "Administrator")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD")


async def _prompt_for_password(default_password: str | None) -> str:
    """Prompt operator for secure admin password when missing."""
    if default_password:
        return default_password

    while True:
        password = getpass("Enter password (min 12 characters): ")
        confirm_password = getpass("Confirm password: ")

        if password != confirm_password:
            print("❌ Passwords do not match. Please try again.")
            continue

        if len(password) < 12:
            print("❌ Password must be at least 12 characters long.")
            continue

        return password


async def create_admin_user(
    auth_service: AuthService,
    *,
    email: str,
    username: str,
    first_name: str,
    last_name: str,
    password: str | None = None,
) -> tuple[bool, dict]:
    """Ensure the default admin user exists via AuthService helper."""
    secret = await _prompt_for_password(password)

    try:
        user = await auth_service.ensure_default_admin(
            email=email, username=username, first_name=first_name, last_name=last_name, password=secret
        )
        payload = user.model_dump(mode="json")
        success = payload.get("role") == "admin" and payload.get("is_active") and payload.get("is_verified")
        return success, payload
    except AuthenticationError as exc:
        return False, {"error": str(exc)}


def _build_postgres_url(host: str) -> str:
    """Compose a PostgreSQL connection string for the given host."""
    user = os.getenv("DATABASE_USER", "krai_user")
    password = os.getenv("DATABASE_PASSWORD", "krai_secure_password")
    port = os.getenv("DATABASE_PORT", os.getenv("POSTGRES_PORT", "5432"))
    database = os.getenv("DATABASE_NAME", os.getenv("POSTGRES_DB", "krai"))
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


async def _initialize_auth_service_with_fallback() -> AuthService:
    """Create AuthService and ensure DB connectivity, falling back to localhost if needed."""
    service = create_auth_service()

    try:
        if hasattr(service, "db") and hasattr(service.db, "connect"):
            await service.db.connect()
        return service
    except Exception as exc:
        error_message = str(exc).lower()
        if "getaddrinfo" not in error_message:
            raise

        print("⚠️  Primary database host unreachable. Attempting localhost fallback…")
        fallback_url = _build_postgres_url("localhost")
        os.environ["DATABASE_CONNECTION_URL"] = fallback_url
        os.environ["POSTGRES_HOST"] = "localhost"

        service = create_auth_service()
        if hasattr(service, "db") and hasattr(service.db, "connect"):
            await service.db.connect()
            print("✅ Connected to PostgreSQL via localhost fallback")
            return service

        raise RuntimeError("Fallback database connection could not be established") from exc


async def main_async(args: argparse.Namespace) -> int:
    """Async entrypoint coordinating admin creation."""
    print("🚀 KRAI Admin User Setup")
    print("=" * 50)

    try:
        auth_service = await _initialize_auth_service_with_fallback()
    except Exception as exc:
        print("❌ Failed to connect to database adapter:", exc)
        return 1

    success, payload = await create_admin_user(
        auth_service,
        email=args.email,
        username=args.username,
        first_name=args.first_name,
        last_name=args.last_name,
        password=args.password or DEFAULT_ADMIN_PASSWORD,
    )

    if success:
        print("\n✨ Admin user setup complete!")
        print(f"Email: {payload.get('email')}")
        print(f"Username: {payload.get('username')}")
        print(f"Role: {payload.get('role')}")
        print("\nYou can now log in to the admin dashboard.")
        return 0

    print("\n❌ Failed to ensure admin user.")
    print(f"Error: {payload.get('error', 'Unknown error')}")
    return 1


def main() -> None:
    """Parse CLI arguments and run async admin creation."""
    parser = argparse.ArgumentParser(description="Create an admin user for the KRAI system.")
    parser.add_argument("--email", default=DEFAULT_ADMIN_EMAIL, help="Admin email address")
    parser.add_argument("--username", default=DEFAULT_ADMIN_USERNAME, help="Admin username")
    parser.add_argument("--first-name", default=DEFAULT_ADMIN_FIRST_NAME, help="Admin first name")
    parser.add_argument("--last-name", default=DEFAULT_ADMIN_LAST_NAME, help="Admin last name")
    parser.add_argument("--password", help="Admin password (will prompt if not provided)")

    args = parser.parse_args()

    exit_code = asyncio.run(main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
