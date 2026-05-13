#!/usr/bin/env python3
import sys

# Read the file
file_path = r"C:\Users\haast\Docker\KRAI-minimal\backend\processors\svg_processor.py"
with open(file_path, encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}", file=sys.stderr)

# Show before state
print("BEFORE (lines 138-195):", file=sys.stderr)
for i in range(137, 195):
    if i < len(lines):
        print(f"{i+1:3}: {lines[i]!r}", file=sys.stderr)

# Step 1: Fix lines 139-150 (0-indexed: 138-149) - add 4 spaces to non-empty lines
print("\nStep 1: Fixing for loop body (lines 139-150)", file=sys.stderr)
for i in range(138, 150):
    if i < len(lines) and lines[i].strip():
        lines[i] = "    " + lines[i]
        print(f"  Fixed line {i+1}", file=sys.stderr)

# Step 2: Fix lines 152-193 (0-indexed: 151-192) - add 4 spaces to all lines
print("\nStep 2: Fixing lines inside try (lines 152-193)", file=sys.stderr)
for i in range(151, 193):
    if i < len(lines):
        lines[i] = "    " + lines[i]
        print(f"  Fixed line {i+1}", file=sys.stderr)

# Step 3: Replace line 193 with finally block
print("\nStep 3: Replace doc.close() with finally block", file=sys.stderr)
if lines[192].strip() == "doc.close()":
    lines[192] = "        finally:\n"
    lines.insert(193, "            doc.close()\n")
    print("  Replaced lines[192] with finally block", file=sys.stderr)

print(f"\nTotal lines after: {len(lines)}", file=sys.stderr)

# Show after state
print("\nAFTER (lines 138-210):", file=sys.stderr)
for i in range(137, min(210, len(lines))):
    print(f"{i+1:3}: {lines[i]!r}", file=sys.stderr)

# Write back
with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print(f"\nFile saved to {file_path}", file=sys.stderr)

# Syntax check
try:
    import py_compile

    py_compile.compile(file_path, doraise=True)
    print("✓ Syntax check PASSED", file=sys.stderr)
except Exception as e:
    print(f"✗ Syntax check FAILED: {e}", file=sys.stderr)
    sys.exit(1)
