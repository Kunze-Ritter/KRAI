"""
Configuration Checker - Prüft ob alle erforderlichen Configs gesetzt sind
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"

print("🔍 Configuration Check")
print("=" * 60)
print(f"Project Root: {project_root}")
print(f".env Path: {env_path}")
print()

if not env_path.exists():
    print("❌ .env file not found!")
    print()
    print("💡 Run setup first:")
    print(f"   cd {project_root}")
    print("   python setup_computer.py")
    sys.exit(1)

load_dotenv(env_path)

# Check required variables
checks = {
    "Database": [
        ("DATABASE_URL", True),
        ("DATABASE_SERVICE_KEY", False),
    ],
    "Object Storage (MinIO/S3-compatible)": [
        ("OBJECT_STORAGE_TYPE", False),
        ("OBJECT_STORAGE_ENDPOINT", True),
        ("OBJECT_STORAGE_ACCESS_KEY", True),
        ("OBJECT_STORAGE_SECRET_KEY", True),
        ("OBJECT_STORAGE_BUCKET_DOCUMENTS", True),
        ("OBJECT_STORAGE_BUCKET_ERROR", False),
        ("OBJECT_STORAGE_BUCKET_PARTS", False),
        ("OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS", False),
        ("OBJECT_STORAGE_PUBLIC_URL_ERROR", False),
        ("OBJECT_STORAGE_PUBLIC_URL_PARTS", False),
        ("OBJECT_STORAGE_USE_SSL", False),
        ("OBJECT_STORAGE_REGION", False),
    ],
    "Ollama": [
        ("OLLAMA_URL", True),
        ("OLLAMA_MODEL_EMBEDDING", True),
        ("OLLAMA_MODEL_TEXT", True),
    ],
    "External APIs (Optional)": [
        ("YOUTUBE_API_KEY", False),
    ],
}

all_ok = True
warnings = []
deprecated_upload_vars = [
    "UPLOAD_IMAGES_TO_R2",
    "UPLOAD_DOCUMENTS_TO_R2",
]

for category, vars_list in checks.items():
    print(f"\n📋 {category}")
    print("-" * 60)

    for var_name, required in vars_list:
        value = os.getenv(var_name)

        if value and value not in [
            "",
            "your_key_here",
            "your_youtube_api_key_here",
            "your_access_key",
            "your_secret_key",
            "your_endpoint",
        ]:
            # Mask sensitive values
            if "KEY" in var_name or "SECRET" in var_name or "TOKEN" in var_name:
                display_value = value[:8] + "..." if len(value) > 8 else "***"
            else:
                display_value = value

            print(f"  ✅ {var_name}: {display_value}")
        else:
            if required:
                print(f"  ❌ {var_name}: NOT SET (REQUIRED)")
                all_ok = False
            else:
                print(f"  ⚠️  {var_name}: NOT SET (optional)")
                warnings.append(var_name)

print("\n🚫 Deprecated R2 Variables")
print("-" * 60)
found_deprecated = [name for name in os.environ if name.startswith("R2_")]
found_deprecated.extend([name for name in deprecated_upload_vars if os.getenv(name)])
found_deprecated = sorted(set(found_deprecated))
if found_deprecated:
    print("  ❌ Legacy R2 variables detected:")
    for name in found_deprecated:
        print(f"     - {name}")
    print("  ❌ Startup will fail while any R2_* variables are present.")
    print("  💡 Migrate to OBJECT_STORAGE_* keys (see docs/MIGRATION_R2_TO_MINIO.md).")
    all_ok = False
else:
    print("  ✅ No deprecated R2_* variables found")

# Check Ollama availability
print("\n🤖 Ollama Status")
print("-" * 60)
try:
    import requests

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    response = requests.get(f"{ollama_url}/api/tags", timeout=2)

    if response.status_code == 200:
        models = response.json().get("models", [])
        print(f"  ✅ Ollama running at {ollama_url}")
        print(f"  📦 Models installed: {len(models)}")
        for model in models:
            print(f"     - {model.get('name')}")
    else:
        print("  ❌ Ollama not responding")
        all_ok = False
except Exception as e:
    print(f"  ❌ Ollama not available: {e}")
    print("     Start with: ollama serve")
    all_ok = False

# Summary
print("\n" + "=" * 60)
if all_ok:
    print("✅ Configuration complete!")
    if warnings:
        print(f"\n⚠️  {len(warnings)} optional settings not configured:")
        for w in warnings:
            print(f"   - {w}")
else:
    print("❌ Configuration incomplete!")
    print("\n💡 Fix required settings and run again")
    sys.exit(1)

print("\n🚀 Ready to process documents!")
