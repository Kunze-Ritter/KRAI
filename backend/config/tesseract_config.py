"""
Tesseract OCR Configuration
Configures pytesseract to find Tesseract binary on Windows
"""

import os
import sys


def configure_tesseract():
    """
    Configure pytesseract with Tesseract binary location
    Call this before using pytesseract
    """
    # Only needed on Windows
    if sys.platform != "win32":
        return

    try:
        import pytesseract

        # Common Tesseract installation paths on Windows
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Tesseract-OCR\tesseract.exe",
        ]

        # Check if already configured or in PATH
        try:
            pytesseract.get_tesseract_version()
            # Already works, no configuration needed
            return
        except:
            pass

        # Find Tesseract executable
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                print(f"✅ Configured Tesseract: {path}")

                # Test if it works now
                try:
                    version = pytesseract.get_tesseract_version()
                    print(f"✅ Tesseract version: {version}")
                    return
                except Exception as e:
                    print(f"⚠️  Configuration test failed: {e}")
                    continue

        print("⚠️  Tesseract not found in common locations")
        print("   Install from: https://github.com/UB-Mannheim/tesseract/wiki")

    except ImportError:
        print("⚠️  pytesseract not installed - run: pip install pytesseract")


if __name__ == "__main__":
    # Test configuration
    configure_tesseract()
