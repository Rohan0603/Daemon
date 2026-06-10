"""Tests for scripts/generate_ast_map.py"""
import ast
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from generate_ast_map import extract_ast_info, generate_codebase_map


def test_extract_ast_info_class_with_methods():
    code = '''
class Foo:
    """Class docstring."""
    def method1(self):
        """Method docstring."""
        pass
    def method2(self, x: int) -> str:
        return str(x)
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        result = extract_ast_info(f.name)
    os.unlink(f.name)

    assert "Foo" in result["classes"]
    assert result["classes"]["Foo"]["docstring"] == "Class docstring."
    assert "method1" in result["classes"]["Foo"]["methods"]
    assert "method2" in result["classes"]["Foo"]["methods"]
    assert result["classes"]["Foo"]["methods"]["method1"]["docstring"] == "Method docstring."
    assert result["classes"]["Foo"]["methods"]["method2"]["args"] == ["self", "x"]


def test_extract_ast_info_standalone_function():
    code = '''
def standalone_func(a, b=1):
    """Function docstring."""
    return a + b
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        result = extract_ast_info(f.name)
    os.unlink(f.name)

    assert "standalone_func" in result["functions"]
    assert result["functions"]["standalone_func"]["docstring"] == "Function docstring."
    assert result["functions"]["standalone_func"]["args"] == ["a", "b"]


def test_extract_ast_info_empty_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("")
        f.flush()
        result = extract_ast_info(f.name)
    os.unlink(f.name)

    assert result["classes"] == {}
    assert result["functions"] == {}
    assert result["docstring"] is None


def test_extract_ast_info_syntax_error():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("this is not valid python @@")
        f.flush()
        result = extract_ast_info(f.name)
    os.unlink(f.name)

    assert result["classes"] == {}
    assert result["functions"] == {}


def test_extract_ast_info_module_docstring():
    code = '''"""Module docstring."""
import os

def helper():
    pass
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        result = extract_ast_info(f.name)
    os.unlink(f.name)

    assert result["docstring"] == "Module docstring."
    assert "helper" in result["functions"]


def test_generate_codebase_map_integration():
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = os.path.join(tmpdir, "src")
        os.makedirs(src_dir)
        with open(os.path.join(src_dir, "sample.py"), "w") as f:
            f.write('class TestClass:\n    """Test docstring."""\n    def test_method(self):\n        pass\n')
        with open(os.path.join(src_dir, "utils.py"), "w") as f:
            f.write('def util_func():\n    """Util docstring."""\n    return 42\n')

        output_file = os.path.join(tmpdir, "map.json")
        generate_codebase_map(src_dir, output_file)

        with open(output_file) as f:
            map_data = json.load(f)

        assert "TestClass" in map_data["classes"]
        assert "test_method" in map_data["classes"]["TestClass"]["methods"]
        assert "util_func" in map_data["functions"]
        assert "utils.py" in str(map_data["modules"])


def test_generate_codebase_map_skips_non_py():
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = os.path.join(tmpdir, "src")
        os.makedirs(src_dir)
        with open(os.path.join(src_dir, "main.py"), "w") as f:
            f.write('def foo(): pass\n')
        with open(os.path.join(src_dir, "data.txt"), "w") as f:
            f.write('not python\n')
        with open(os.path.join(src_dir, "module.py"), "w") as f:
            f.write('class Bar: pass\n')

        output_file = os.path.join(tmpdir, "map.json")
        generate_codebase_map(src_dir, output_file)

        with open(output_file) as f:
            map_data = json.load(f)

        assert "foo" in map_data["functions"]
        assert "Bar" in map_data["classes"]
        assert "data.txt" not in str(map_data["modules"])
