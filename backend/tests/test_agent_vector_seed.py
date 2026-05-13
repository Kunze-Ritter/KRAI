"""
Tests that verify KRAIAgent and create_tools accept ai_service and reranking_service params.
Uses AST parsing to avoid importing the module (which has heavy dependencies like langgraph).
"""

import ast
from pathlib import Path

AGENT_API_PATH = Path(__file__).parent.parent / "api" / "agent_api.py"


def _get_function_params(source: str, func_name: str) -> list[str]:
    """Return parameter names for a top-level function definition in source."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            args = node.args
            return [a.arg for a in args.args]
    return []


def _get_method_params(source: str, class_name: str, method_name: str) -> list[str]:
    """Return parameter names for a method inside a class definition."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    args = item.args
                    return [a.arg for a in args.args]
    return []


def test_create_tools_accepts_ai_service_and_reranking_service():
    """create_tools must accept ai_service and reranking_service parameters."""
    source = AGENT_API_PATH.read_text(encoding="utf-8")
    params = _get_function_params(source, "create_tools")
    assert "ai_service" in params, f"create_tools missing ai_service param. Got: {params}"
    assert "reranking_service" in params, f"create_tools missing reranking_service param. Got: {params}"


def test_kraiagent_init_accepts_ai_service_and_reranking_service():
    """KRAIAgent.__init__ must accept ai_service and reranking_service parameters."""
    source = AGENT_API_PATH.read_text(encoding="utf-8")
    params = _get_method_params(source, "KRAIAgent", "__init__")
    assert "ai_service" in params, f"KRAIAgent.__init__ missing ai_service param. Got: {params}"
    assert "reranking_service" in params, f"KRAIAgent.__init__ missing reranking_service param. Got: {params}"
