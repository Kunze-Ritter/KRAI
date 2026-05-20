"""
Ollama Setup Verification Script
Tests Ollama installation, models, and GPU detection
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from backend.utils.colored_logging import apply_colored_logging_globally, error, info, success, warning
from backend.utils.gpu_detector import print_gpu_info

# Setup colored logging
apply_colored_logging_globally(level=logging.INFO)
logger = logging.getLogger("krai.ollama_test")


async def test_ollama_connection(url: str = "http://localhost:11434") -> bool:
    """Test basic Ollama connection"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{url}/api/tags")
            if response.status_code == 200:
                return True
            error(f"Ollama API returned status {response.status_code}")
            return False
    except Exception as e:
        error(f"Failed to connect to Ollama: {e}")
        return False


async def get_installed_models(url: str = "http://localhost:11434") -> list:
    """Get list of installed models"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return data.get("models", [])
            return []
    except Exception as e:
        error(f"Failed to get models: {e}")
        return []


async def test_model(url: str, model: str) -> bool:
    """Test if a specific model works"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{url}/api/generate",
                json={
                    "model": model,
                    "prompt": "Hello, this is a test. Reply with 'OK' if you can read this.",
                    "stream": False,
                },
            )
            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "")
                success(f"Model {model} responded: {response_text[:50]}...")
                return True
            error(f"Model {model} returned status {response.status_code}")
            return False
    except Exception as e:
        error(f"Failed to test model {model}: {e}")
        return False


async def main():
    """Main verification routine"""
    print("\n" + "=" * 60)
    print("🔍 OLLAMA SETUP VERIFICATION")
    print("=" * 60 + "\n")

    # Step 1: GPU Detection
    info("Step 1: Detecting GPU...")
    gpu_info = print_gpu_info()

    # Step 2: Test Ollama Connection
    info("\nStep 2: Testing Ollama connection...")
    connection_ok = await test_ollama_connection()

    if connection_ok:
        success("✓ Ollama is running and responding")
    else:
        error("✗ Ollama is not responding")
        print("\nTo start Ollama:")
        print("  Windows: Start Ollama from Start Menu")
        print("  Or run: %LOCALAPPDATA%\\Programs\\Ollama\\ollama.exe serve")
        return

    # Step 3: Check installed models
    info("\nStep 3: Checking installed models...")
    models = await get_installed_models()

    if models:
        success(f"✓ Found {len(models)} installed models:")
        for model in models:
            print(f"  - {model['name']} ({model.get('size', 0) / 1e9:.1f} GB)")
    else:
        warning("⚠ No models installed")

    # Step 4: Check for required models
    info("\nStep 4: Verifying required models...")

    required_models = {
        "vision": gpu_info["recommended_vision_model"],
        "text": "llama3.2:latest",
        "embeddings": "nomic-embed-text:latest",
    }

    installed_model_names = [m["name"] for m in models]

    for model_type, model_name in required_models.items():
        # Check for exact match or base name match
        model_found = any(
            model_name in installed_name or installed_name.startswith(model_name.split(":")[0])
            for installed_name in installed_model_names
        )

        if model_found:
            success(f"✓ {model_type.capitalize()} model available")
        else:
            warning(f"⚠ {model_type.capitalize()} model ({model_name}) not installed")
            print(f"  Install with: ollama pull {model_name}")

    # Step 5: Test vision model
    info("\nStep 5: Testing vision model...")
    vision_model = gpu_info["recommended_vision_model"]

    # Check if vision model is installed
    vision_installed = any(
        vision_model in m["name"] or m["name"].startswith(vision_model.split(":")[0]) for m in models
    )

    if vision_installed:
        success(f"✓ Vision model {vision_model} is installed")

        # Test it
        info(f"  Testing {vision_model} (this may take a moment)...")
        test_ok = await test_model("http://localhost:11434", vision_model)

        if test_ok:
            success("✓ Vision model is working correctly")
        else:
            error("✗ Vision model test failed")
    else:
        warning(f"⚠ Recommended vision model {vision_model} not installed")
        print("\nTo install the recommended model:")
        print(f"  ollama pull {vision_model}")
        print("\nOr run the automated installer:")
        print("  fix_ollama_gpu.bat")

    # Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    print(f"GPU: {gpu_info['gpu_name']}")
    print(f"VRAM: {gpu_info['vram_gb']:.1f} GB")
    print(f"Recommended Model: {gpu_info['recommended_vision_model']}")
    print(f"Ollama Status: {'✓ Running' if connection_ok else '✗ Not Running'}")
    print(f"Installed Models: {len(models)}")
    print("=" * 60 + "\n")

    # Next steps
    if vision_installed and connection_ok:
        success("🎉 Everything looks good! You're ready to go.")
        print("\nYou can now run the pipeline:")
        print("  cd backend\\tests")
        print("  python krai_master_pipeline.py")
    else:
        warning("⚠ Some setup steps are missing")
        print("\nRecommended actions:")
        if not connection_ok:
            print("  1. Start Ollama service")
        if not vision_installed:
            print(f"  2. Run: ollama pull {vision_model}")
            print("     Or run: fix_ollama_gpu.bat")
        print("  3. Re-run this verification: python test_ollama_setup.py")


if __name__ == "__main__":
    asyncio.run(main())
