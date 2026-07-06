"""Issue 07 — the generation↔consumption boundary is held by import direction.

ADR 0006's separation survives co-hosting because the reader module and the
generation module never import each other; the boundary is enforced here by
statically walking the imports of each package (ADR 0014, ADR 0015).
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

READER_API_MODULES = ("reader.py", "dtos.py", "dependencies.py", "errors.py", "identity.py")


def _top_level_imports(path: Path) -> set[str]:
    """Return the top-level package name of every import in a module."""
    tree = ast.parse(path.read_text())
    packages: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            packages.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            packages.add(node.module.split(".")[0])
    return packages


def _imports_of_package(package: str) -> dict[Path, set[str]]:
    """Map each module in a src package to the top-level packages it imports."""
    return {path: _top_level_imports(path) for path in (SRC / package).rglob("*.py")}


def test_consumption_imports_no_generation_and_no_api() -> None:
    for path, packages in _imports_of_package("consumption").items():
        assert "harness" not in packages, f"{path} imports generation code"
        assert "api" not in packages, f"{path} imports the api layer"


def test_harness_imports_no_consumption_and_no_api() -> None:
    for path, packages in _imports_of_package("harness").items():
        assert "consumption" not in packages, f"{path} imports reader code"
        assert "api" not in packages, f"{path} imports the api layer"


def test_reader_facing_api_modules_import_no_generation() -> None:
    for name in READER_API_MODULES:
        packages = _top_level_imports(SRC / "api" / name)
        assert "harness" not in packages, f"api/{name} imports generation code"


def test_only_the_composition_root_reaches_the_harness() -> None:
    reach = {
        path.name for path, packages in _imports_of_package("api").items() if "harness" in packages
    }

    assert reach <= {"harness_runner.py", "main.py"}, f"unexpected harness importers: {reach}"


GENERATION_ONLY_SYMBOLS = ("run_agent", "ToolSpec", "LLMConfig", "usage.json", "fan_out")


def test_consumption_references_none_of_the_generation_only_symbols() -> None:
    for path in (SRC / "consumption").rglob("*.py"):
        text = path.read_text()
        for symbol in GENERATION_ONLY_SYMBOLS:
            assert symbol not in text, f"{path} references generation-only {symbol!r}"
