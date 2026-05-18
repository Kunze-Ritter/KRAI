import py_compile
import sys

try:
    py_compile.compile(r"C:\Users\haast\Docker\KRAI-minimal\backend\processors\svg_processor.py", doraise=True)
    print("✓ Indentation fixed and syntax validated")
except py_compile.PyCompileError as e:
    print(f"✗ Syntax error: {e}")
    sys.exit(1)
