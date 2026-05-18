#!/usr/bin/env python3
import ast

files = [
    "backend/processors/image_processor.py",
    "backend/processors/svg_processor.py",
    "backend/api/routes/batch.py",
    "backend/api/routes/auth.py",
]

for f in files:
    try:
        with open(f, encoding="utf-8") as file:
            ast.parse(file.read())
        print(f"{f}: OK")
    except SyntaxError as e:
        print(f"{f}: {e}")
    except Exception as e:
        print(f"{f}: {type(e).__name__}: {e}")
