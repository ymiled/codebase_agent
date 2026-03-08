import os
import ast
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# write_to_file_tool — path validation logic
# ---------------------------------------------------------------------------

class TestWritePathValidation:
    """Test the realpath-based path validation used by write_to_file_tool."""

    def _is_allowed(self, file_path: str) -> bool:
        """Replicate the validation logic from write_to_file_tool."""
        real_path = os.path.realpath(file_path)
        allowed_dir = os.path.realpath("target_repo")
        return real_path.startswith(allowed_dir + os.sep) or real_path == allowed_dir

    def test_allows_target_repo_file(self):
        assert self._is_allowed("target_repo/bad_code_1.py") is True

    def test_allows_nested_target_repo_file(self):
        assert self._is_allowed("target_repo/sub/module.py") is True

    def test_blocks_path_traversal(self):
        # ../target_repo/../etc/passwd should resolve outside target_repo
        assert self._is_allowed("../target_repo/../etc/passwd") is False

    def test_blocks_absolute_outside_path(self):
        assert self._is_allowed("/tmp/malicious.py") is False

    def test_blocks_parent_directory_escape(self):
        assert self._is_allowed("target_repo/../main.py") is False

    def test_blocks_unrelated_path_containing_substring(self):
        # A path like "not_target_repo/file.py" should be blocked even though
        # the old check ("target_repo" in path) would have allowed it
        assert self._is_allowed("not_target_repo/file.py") is False


# ---------------------------------------------------------------------------
# analyze_dependencies_tool — AST import parsing logic
# ---------------------------------------------------------------------------

class TestDependencyParsing:
    """Test the AST-based import parsing used by analyze_dependencies_tool."""

    def test_extracts_imports(self, tmp_path):
        code = """\
import os
import sys
from pathlib import Path
from collections import Counter

def my_function():
    pass

class MyClass:
    pass
"""
        f = tmp_path / "sample.py"
        f.write_text(code, encoding="utf-8")

        tree = ast.parse(code)
        imports = set()
        functions = set()
        classes = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
            elif isinstance(node, ast.FunctionDef):
                functions.add(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.add(node.name)

        assert "os" in imports
        assert "sys" in imports
        assert "pathlib" in imports
        assert "collections" in imports
        assert "my_function" in functions
        assert "MyClass" in classes

    def test_handles_syntax_error(self):
        bad_code = "def broken(:\n    pass"
        with pytest.raises(SyntaxError):
            ast.parse(bad_code)


# ---------------------------------------------------------------------------
# Cross-file dependency detection logic
# ---------------------------------------------------------------------------

class TestCrossFileDependencyDetection:
    """Test the logic that finds files importing a target module."""

    def test_finds_dependent_files(self, tmp_path):
        # Create a "target" module
        target = tmp_path / "deps_shared.py"
        target.write_text("def shared_func(): pass\n", encoding="utf-8")

        # Create a file that imports from target
        dependent = tmp_path / "deps_a.py"
        dependent.write_text("from deps_shared import shared_func\n", encoding="utf-8")

        # Create a file that does NOT import from target
        unrelated = tmp_path / "other.py"
        unrelated.write_text("import os\n", encoding="utf-8")

        # Replicate the detection logic
        target_name = "deps_shared"
        dependents = []
        for f in tmp_path.glob("*.py"):
            if f.name == "deps_shared.py":
                continue
            content = f.read_text(encoding="utf-8")
            if target_name in content and (
                "import " + target_name in content or "from " + target_name in content
            ):
                dependents.append(f.name)

        assert "deps_a.py" in dependents
        assert "other.py" not in dependents

    def test_no_dependents(self, tmp_path):
        target = tmp_path / "isolated.py"
        target.write_text("x = 1\n", encoding="utf-8")

        target_name = "isolated"
        dependents = []
        for f in tmp_path.glob("*.py"):
            if f.name == "isolated.py":
                continue
            content = f.read_text(encoding="utf-8")
            if target_name in content:
                dependents.append(f.name)

        assert dependents == []
