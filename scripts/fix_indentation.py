#!/usr/bin/env python3
"""Fix indentation errors in svg_processor.py"""

# Read the file
file_path = r"C:\Users\haast\Docker\KRAI-minimal\backend\processors\svg_processor.py"
with open(file_path, encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines before: {len(lines)}")
print("\n--- BEFORE CHANGES ---")
print("Lines 138-150:")
for i in range(138, 150):
    print(f"Line {i+1:3d}: {lines[i]!r}")

print("\nLines 151-195:")
for i in range(151, 195):
    print(f"Line {i+1:3d}: {lines[i]!r}")

# Step 1: Add 4 spaces to lines 138-149 (view lines 139-150)
# These lines are inside the for loop body
print("\n--- STEP 1: Fixing lines 139-150 (0-indexed 138-149) ---")
for i in range(138, 150):
    if lines[i].strip():  # non-empty lines
        lines[i] = "    " + lines[i]
        print(f"Line {i+1:3d}: Added 4 spaces")

# Step 2: Add 4 spaces to lines 151-192 (view lines 152-193)
# These lines should be inside the try block
print("\n--- STEP 2: Fixing lines 152-193 (0-indexed 151-192) ---")
for i in range(151, 193):
    lines[i] = "    " + lines[i]
    print(f"Line {i+1:3d}: Added 4 spaces")

# Step 3: Replace line 192 (doc.close()) with finally block
print("\n--- STEP 3: Replace doc.close() with finally block ---")
print(f"Line 193 before: {lines[192]!r}")
lines[192] = "        finally:\n"
lines.insert(193, "            doc.close()\n")
print(f"Line 193 after: {lines[192]!r}")
print(f"Line 194 after: {lines[193]!r}")

print(f"\nTotal lines after: {len(lines)}")

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print(f"\nFile written back to {file_path}")

# Verify by reading again
with open(file_path, encoding="utf-8") as f:
    lines = f.readlines()

print("\n--- VERIFICATION ---")
print("Lines 130-215 (0-indexed, showing 1-indexed line numbers):")
for i in range(128, min(215, len(lines))):
    print(f"Line {i+1:3d}: {lines[i]}", end="")

print("\n\n--- RUNNING SYNTAX CHECK ---")
import py_compile
import sys

try:
    py_compile.compile(file_path, doraise=True)
    print(f"✓ Syntax check passed for {file_path}")
except py_compile.PyCompileError as e:
    print(f"✗ Syntax error: {e}")
    sys.exit(1)
