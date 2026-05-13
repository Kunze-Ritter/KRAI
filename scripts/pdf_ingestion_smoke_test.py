"""PDF ingestion smoke test script for local pipeline validation."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

DEFAULT_PDF_PATH = Path("/app/temp/pdf_smoke_test.pdf")
DEFAULT_POLL_INTERVAL = 5.0
DEFAULT_MAX_POLLS = 12


def parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _print_json(label: str, payload: dict[str, Any]) -> None:
    print(label)
    print(json.dumps(payload, indent=2, default=str))


def main() -> int:
    base_url = os.getenv("AUTH_BASE_URL", "http://localhost:8000").rstrip("/")
    username = os.getenv("AUTH_TEST_USERNAME") or os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    password = os.getenv("AUTH_TEST_PASSWORD") or os.getenv("DEFAULT_ADMIN_PASSWORD")
    remember_me = parse_bool(os.getenv("AUTH_TEST_REMEMBER"))

    pdf_path = Path(os.getenv("PDF_SMOKE_TEST_PATH", str(DEFAULT_PDF_PATH)))
    document_type = os.getenv("PDF_SMOKE_DOCUMENT_TYPE", "service_manual")
    language = os.getenv("PDF_SMOKE_LANGUAGE", "en")
    poll_interval = float(os.getenv("PDF_SMOKE_POLL_INTERVAL", str(DEFAULT_POLL_INTERVAL)))
    max_polls = int(os.getenv("PDF_SMOKE_MAX_POLLS", str(DEFAULT_MAX_POLLS)))

    if not password:
        print(
            "ERROR: Admin password not provided via AUTH_TEST_PASSWORD or DEFAULT_ADMIN_PASSWORD.",
            file=sys.stderr,
        )
        return 2

    if not pdf_path.exists():
        print(f"ERROR: PDF file not found at {pdf_path}", file=sys.stderr)
        return 3

    login_payload = {
        "username": username,
        "password": password,
        "remember_me": remember_me,
    }

    login_url = f"{base_url}/api/v1/auth/login"
    print(f"POST {login_url}")
    _print_json("Login payload:", {**login_payload, "password": "***"})

    try:
        login_response = requests.post(login_url, json=login_payload, timeout=15)
    except requests.RequestException as exc:  # pragma: no cover - runtime diagnostics
        print(f"Login request failed: {exc}", file=sys.stderr)
        return 4

    print(f"Login status: {login_response.status_code}")
    print(login_response.text)

    if login_response.status_code != 200:
        return 5

    try:
        login_json = login_response.json()
    except json.JSONDecodeError as exc:
        print(f"Invalid login JSON response: {exc}", file=sys.stderr)
        return 6

    tokens = login_json.get("data", {})
    access_token = tokens.get("access_token")
    if not access_token:
        print("Missing access token in login response", file=sys.stderr)
        return 7

    headers = {"Authorization": f"Bearer {access_token}"}

    upload_url = f"{base_url}/api/v1/documents/upload"
    print(f"\nPOST {upload_url}")
    print(f"Uploading file: {pdf_path} ({pdf_path.stat().st_size} bytes)")

    try:
        with pdf_path.open("rb") as file_handle:
            files = {"file": (pdf_path.name, file_handle, "application/pdf")}
            data = {"document_type": document_type, "language": language}
            upload_response = requests.post(
                upload_url,
                headers=headers,
                files=files,
                data=data,
                timeout=120,
            )
    except requests.RequestException as exc:
        print(f"Upload request failed: {exc}", file=sys.stderr)
        return 8

    print(f"Upload status: {upload_response.status_code}")
    print(upload_response.text)

    if upload_response.status_code != 200:
        return 9

    try:
        upload_json = upload_response.json()
    except json.JSONDecodeError as exc:
        print(f"Invalid upload JSON response: {exc}", file=sys.stderr)
        return 10

    _print_json("Upload response JSON:", upload_json)

    document_id = (
        upload_json.get("document_id")
        or upload_json.get("data", {}).get("document_id")
        or upload_json.get("data", {}).get("id")
    )
    if not document_id:
        print("Missing document_id in upload response", file=sys.stderr)
        return 11

    status_url = f"{base_url}/api/v1/documents/{document_id}/status"
    print(f"\nPolling status: {status_url}")

    last_status: dict[str, Any] = {}
    for attempt in range(1, max_polls + 1):
        try:
            status_response = requests.get(status_url, headers=headers, timeout=15)
        except requests.RequestException as exc:
            print(f"Status request failed (attempt {attempt}): {exc}", file=sys.stderr)
            time.sleep(poll_interval)
            continue

        print(f"Status attempt {attempt}: {status_response.status_code}")
        try:
            last_status = status_response.json()
        except json.JSONDecodeError:
            print(status_response.text)
            time.sleep(poll_interval)
            continue

        _print_json("Status response:", last_status)

        doc_status = (last_status.get("document_status") or last_status.get("status") or "").lower()
        if doc_status in {"completed", "processed", "succeeded", "failed", "error"}:
            break

        time.sleep(poll_interval)

    else:
        print("Status polling timed out without terminal state", file=sys.stderr)
        return 12

    final_status = last_status.get("document_status") or last_status.get("status")
    print(f"\nFinal document status: {final_status}")
    print(f"Document ID: {document_id}")

    output_path = Path("/app/temp/pdf_smoke_test_doc_id.txt")
    output_path.write_text(document_id, encoding="utf-8")
    print(f"Stored document ID at {output_path}")

    if isinstance(final_status, str) and final_status.lower() in {"failed", "error"}:
        return 13

    return 0


if __name__ == "__main__":
    sys.exit(main())
