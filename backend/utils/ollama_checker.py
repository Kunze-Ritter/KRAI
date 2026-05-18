"""Ollama Checker

Checks if Ollama is running and optionally starts it.
"""

import platform
import subprocess
import time

import requests


def check_ollama_running(timeout: int = 2) -> bool:
    """
    Check if Ollama is running

    Args:
        timeout: Request timeout in seconds

    Returns:
        True if Ollama is running
    """
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=timeout)
        return response.status_code == 200
    except:
        return False


def start_ollama() -> tuple[bool, str]:
    """
    Try to start Ollama

    Returns:
        Tuple of (success, message)
    """
    system = platform.system()

    try:
        if system == "Windows":
            # Try to start Ollama on Windows
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # Linux/Mac
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Wait a bit for Ollama to start
        time.sleep(3)

        # Check if it's running now
        if check_ollama_running():
            return True, "✅ Ollama started successfully"
        return False, "⚠️ Ollama started but not responding yet (may need more time)"

    except FileNotFoundError:
        return False, "❌ Ollama not found. Please install: https://ollama.ai"
    except Exception as e:
        return False, f"❌ Failed to start Ollama: {e}"


def ensure_ollama_running(auto_start: bool = True) -> tuple[bool, str]:
    """
    Ensure Ollama is running, optionally start it

    Args:
        auto_start: If True, try to start Ollama if not running

    Returns:
        Tuple of (is_running, message)
    """
    # Check if already running
    if check_ollama_running():
        return True, "✅ Ollama is running"

    # Not running
    if not auto_start:
        return False, (
            "❌ Ollama is not running!\n"
            "   Please start it manually: ollama serve\n"
            "   Or install from: https://ollama.ai"
        )

    # Try to start
    print("🔄 Ollama not running, attempting to start...")
    success, message = start_ollama()

    if not success:
        message += "\n   Please start manually: ollama serve"

    return success, message


def get_ollama_models() -> list:
    """
    Get list of available Ollama models

    Returns:
        List of model names
    """
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        return []
    except:
        return []


if __name__ == "__main__":
    # Test
    print("Checking Ollama...")
    is_running, message = ensure_ollama_running(auto_start=True)
    print(message)

    if is_running:
        models = get_ollama_models()
        print(f"\nAvailable models: {', '.join(models) if models else 'None'}")
