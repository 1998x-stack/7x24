"""Verify built wheels are self-contained and exclude archived implementation.

Usage: python scripts/verify_wheel.py dist/
"""

import sys
import zipfile
from pathlib import Path


def check_wheel(directory: Path) -> None:
    wheels = sorted(directory.glob("news24-*.whl"))
    if len(wheels) != 1:
        raise ValueError(f"expected one news24 wheel in {directory}, got {len(wheels)}")
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
    required = {
        "news24/domain/news.py",
        "news24/domain/errors.py",
        "news24/application/intelligence/service.py",
        "news24/application/jobs/worker.py",
        "news24/infrastructure/sqlite/database.py",
        "news24/infrastructure/llm/openai_responses.py",
        "news24/interfaces/cli.py",
        "news24/interfaces/web/index.html",
        "news24/interfaces/web/app.css",
        "news24/interfaces/web/app.js",
        "news24/infrastructure/sqlite/migrations/0001_initial.sql",
        "news24/infrastructure/sqlite/migrations/0002_jobs.sql",
        "news24/infrastructure/sqlite/migrations/0003_intelligence.sql",
        "news24/infrastructure/sqlite/migrations/0004_review.sql",
        "news24/cli.py",  # backward-compatible import facade
    }
    missing = sorted(required - names)
    if missing:
        raise ValueError("missing package resources: " + ", ".join(missing))
    unexpected = sorted(
        n for n in names
        if n.startswith(("legacy/", "src/", "tests/", "examples/"))
        or n.startswith("news24/web/") and n.endswith((".js", ".css", ".html"))
        or n.startswith("news24/storage/migrations/") and n.endswith(".sql")
    )
    if unexpected:
        raise ValueError("unexpected legacy or duplicate wheel members: " + ", ".join(unexpected))
    print(f"OK: {wheels[0].name}, {len(names)} files, "
          f"{len(required)} required resources, no archived runtime content")


if __name__ == "__main__":
    check_wheel(Path(sys.argv[1] if len(sys.argv) > 1 else "dist"))
