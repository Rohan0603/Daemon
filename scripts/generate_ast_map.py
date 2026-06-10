#!/usr/bin/env python3
"""Generate AST-based codebase map for Daemon self-awareness.

Outputs data/codebase_map.json with:
- classes: {ClassName: {docstring, methods: {methodName: {docstring, args, returns}}}}
- functions: {funcName: {docstring, args, returns}}
- modules: {modulePath: {docstring, classes: [], functions: []}}
"""

import ast
import json
import os
import sys
from pathlib import Path


def extract_ast_info(file_path: str) -> dict:
    """Extract classes, functions, and docstrings from a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
    except (OSError, UnicodeDecodeError):
        return {"classes": {}, "functions": {}, "docstring": None}

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return {"classes": {}, "functions": {}, "docstring": None}

    result = {"classes": {}, "functions": {}, "docstring": ast.get_docstring(tree)}

    method_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_info = {
                "docstring": ast.get_docstring(node),
                "methods": {},
                "bases": [base.id if isinstance(base, ast.Name) else "..." for base in node.bases]
            }
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    method_names.add(item.name)
                    method_info = {
                        "docstring": ast.get_docstring(item),
                        "args": [arg.arg for arg in item.args.args],
                        "returns": ast.unparse(item.returns) if item.returns else None
                    }
                    class_info["methods"][item.name] = method_info
            result["classes"][node.name] = class_info

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name not in method_names:
            func_info = {
                "docstring": ast.get_docstring(node),
                "args": [arg.arg for arg in node.args.args],
                "returns": ast.unparse(node.returns) if node.returns else None
            }
            result["functions"][node.name] = func_info

    return result


def generate_codebase_map(src_root: str, output_path: str) -> None:
    """Walk src directory, extract AST info, write compressed JSON map."""
    src_path = Path(src_root)
    if not src_path.exists():
        print(f"Source root not found: {src_root}", file=sys.stderr)
        sys.exit(1)

    all_classes = {}
    all_functions = {}
    modules = {}

    for py_file in sorted(src_path.rglob("*.py")):
        if "__pycache__" in py_file.parts or ".pytest_cache" in py_file.parts:
            continue

        rel_path = str(py_file.relative_to(src_path.parent))
        info = extract_ast_info(str(py_file))

        modules[rel_path] = {
            "docstring": info["docstring"],
            "classes": list(info["classes"].keys()),
            "functions": list(info["functions"].keys())
        }
        all_classes.update(info["classes"])
        all_functions.update(info["functions"])

    map_data = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "project_root": str(src_path.parent),
        "modules": modules,
        "classes": all_classes,
        "functions": all_functions
    }

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(map_data, f, indent=2)

    print(f"Codebase map written to {output_path} ({len(all_classes)} classes, {len(all_functions)} functions)")


if __name__ == "__main__":
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    src_dir = os.path.join(project_root, "src")
    output_file = os.path.join(project_root, "data", "codebase_map.json")
    generate_codebase_map(src_dir, output_file)
