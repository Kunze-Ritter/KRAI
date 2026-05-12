"""Guard against duplicate registration of /api/v1/documents/{document_id}/stages.

Two router files used to register the same path:
  - backend/api/routes/documents.py            (structured response, wins)
  - backend/api/routes/document_processing.py  (flat-string response, dead code)

FastAPI silently uses the first registered handler, so the Laravel side never
saw the structured payload. This test parses both source files via ast and
fails if more than one @router.get decorator matches the path.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _route_paths_in(file_path: Path) -> list[tuple[str, str]]:
    """Return (method, path) tuples for every @router.<method>(...) decorator
    in the file. Path is the literal string passed as the first positional
    argument (no router prefix applied).
    """
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    results: list[tuple[str, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        for deco in node.decorator_list:
            if not isinstance(deco, ast.Call):
                continue
            func = deco.func
            if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)):
                continue
            if func.value.id != "router":
                continue
            method = func.attr.lower()
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not deco.args:
                continue
            first = deco.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                results.append((method, first.value))

    return results


def _router_prefix(file_path: Path) -> str:
    """Extract the prefix kwarg from the APIRouter(...) call in the file (if any)."""
    match = re.search(r'APIRouter\([^)]*prefix\s*=\s*["\']([^"\']+)["\']', file_path.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def _full_paths(file_path: Path) -> list[tuple[str, str]]:
    prefix = _router_prefix(file_path)
    return [(method, f"{prefix}{path}") for method, path in _route_paths_in(file_path)]


def test_stages_endpoint_registered_only_once_across_route_files():
    documents_paths = _full_paths(ROOT / "api" / "routes" / "documents.py")
    processing_paths = _full_paths(ROOT / "api" / "routes" / "document_processing.py")

    all_paths = documents_paths + processing_paths

    stages_get = [
        (method, path)
        for method, path in all_paths
        if method == "get" and re.fullmatch(r"/documents/\{[^}]+\}/stages", path)
    ]

    assert len(stages_get) == 1, (
        f"Expected exactly one GET handler for /documents/{{id}}/stages, " f"got {len(stages_get)}: {stages_get}"
    )
