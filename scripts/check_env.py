#!/usr/bin/env python
import subprocess
import sys

checks = [
    ("Python version", [sys.executable, "--version"]),
    ("langchain", [sys.executable, "-c", "import langchain; print(f'langchain: {langchain.__version__}')"]),
    ("langgraph", [sys.executable, "-c", "import langgraph; print(f'langgraph: {langgraph.__version__}')"]),
    ("langchain_ollama", [sys.executable, "-c", "import langchain_ollama; print('langchain_ollama: ok')"]),
]

for name, cmd in checks:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✓ {name}: {result.stdout.strip()}")
        else:
            print(f"✗ {name}: ERROR - {result.stderr.strip()}")
    except Exception as e:
        print(f"✗ {name}: {e!s}")

# Check Ollama
print("\nChecking Ollama connectivity...")
try:
    import requests

    response = requests.get("http://localhost:11434/api/tags", timeout=5)
    if response.status_code == 200:
        print(f"✓ Ollama API: Running (status {response.status_code})")
    else:
        print(f"✗ Ollama API: Error (status {response.status_code})")
except requests.exceptions.ConnectionError:
    print("✗ Ollama API: Not responding (connection refused)")
except Exception as e:
    print(f"✗ Ollama API: {e!s}")
