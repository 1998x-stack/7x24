"""Architecture contracts for the modular-monolith package.

This suite prevents accidental moves of business/domain code back into legacy
modules and forbids new cycles or reverse dependencies between top-level layers.
"""

import ast
import tomllib
from importlib import resources
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "src" / "news24"
LAYERS = ("domain", "application", "infrastructure", "interfaces")
DEPRECATED = (
    "news24.core", "news24.ingestion", "news24.intelligence",
    "news24.jobs", "news24.sources", "news24.storage",
    "news24.reporting", "news24.review", "news24.evaluation",
    "news24.observability", "news24.web",
)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(item.name for item in node.names)
    return modules


def test_canonical_modules_do_not_depend_on_compatibility_facades() -> None:
    visited = 0
    for layer in LAYERS:
        for path in (PACKAGE_ROOT / layer).rglob("*.py"):
            visited += 1
            imports = _imports(path)
            for module in imports:
                assert not any(
                    module == deprecated or module.startswith(deprecated + ".")
                    for deprecated in DEPRECATED
                ), f"{path}: old compatibility module referenced by canonical code: {module}"
    assert visited >= 20


def test_layer_directions() -> None:
    """Domain cannot depend on adapters/application/interfaces; inner layers never import UI."""
    for path in (PACKAGE_ROOT / "domain").rglob("*.py"):
        for imp in _imports(path):
            if imp.startswith("news24."):
                assert imp.startswith("news24.domain."), (path, imp)
    for layer in ("application", "infrastructure"):
        for path in (PACKAGE_ROOT / layer).rglob("*.py"):
            for imp in _imports(path):
                assert not imp.startswith("news24.interfaces."), (path, imp)


def test_no_direct_import_cycle_between_canonical_modules() -> None:
    paths = {
        "news24." + ".".join(path.relative_to(PACKAGE_ROOT).with_suffix("").parts): path
        for layer in LAYERS
        for path in (PACKAGE_ROOT / layer).rglob("*.py")
    }
    graph: dict[str, set[str]] = {name: set() for name in paths}
    for name, path in paths.items():
        for imported in _imports(path):
            if imported in graph and imported != name:
                graph[name].add(imported)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        assert name not in visiting, f"cyclic import chain includes: {name}"
        visiting.add(name)
        for dependency in graph[name]:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)

    for name in graph:
        visit(name)


def test_deprecated_imports_are_identity_preserving() -> None:
    from news24.cli import main as old_main
    from news24.core.models import NewsArticle as OldArticle
    from news24.domain.news import NewsArticle as CurrentArticle
    from news24.infrastructure.sqlite.database import SQLiteNewsStore as CurrentStore
    from news24.interfaces.cli import main as current_main
    from news24.storage.database import SQLiteNewsStore as OldStore

    assert old_main is current_main
    assert OldArticle is CurrentArticle
    assert OldStore is CurrentStore


def test_packaged_sql_and_web_assets_have_single_canonical_source() -> None:
    migration = resources.files("news24.infrastructure.sqlite.migrations")
    ui = resources.files("news24.interfaces.web")
    for name in (
        "0001_initial.sql", "0002_jobs.sql", "0003_intelligence.sql", "0004_review.sql"
    ):
        assert "CREATE TABLE" in migration.joinpath(name).read_text(encoding="utf-8")
    assert "<!doctype html>" in ui.joinpath("index.html").read_text(encoding="utf-8")
    assert "textContent" in ui.joinpath("app.js").read_text(encoding="utf-8")
    assert ":root" in ui.joinpath("app.css").read_text(encoding="utf-8")


def test_installable_distribution_excludes_legacy_tree() -> None:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    finder = data["tool"]["setuptools"]["packages"]["find"]
    assert finder["where"] == ["src"]
    assert finder["include"] == ["news24*"]
    assert "news24.interfaces.web" in data["tool"]["setuptools"]["package-data"]
    assert "news24.infrastructure.sqlite.migrations" in data["tool"]["setuptools"]["package-data"]
    assert (PROJECT_ROOT / "legacy" / "src" / "main.py").is_file()
    assert (PROJECT_ROOT / "tests" / "legacy" / "test_system.py").is_file()
