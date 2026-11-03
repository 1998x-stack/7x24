"""Stable command line entrypoint: explicit exit codes and machine-readable results."""

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from news24 import __version__
from news24.core.errors import News24Error
from news24.core.models import NewsArticle
from news24.sources.sina.client import fetch_latest
from news24.sources.sina.parser import parse_feed, parse_payload


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _doctor(args: argparse.Namespace) -> int:
    data_dir = Path(os.getenv("NEWS24_DATA_DIR", "./data")).resolve()
    checks: dict[str, bool] = {}
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=data_dir):
            pass
        checks["data_dir_writable"] = True
    except OSError:
        checks["data_dir_writable"] = False

    try:
        with sqlite3.connect(":memory:") as connection:
            connection.execute("CREATE VIRTUAL TABLE probe USING fts5(body, tokenize='trigram')")
        checks["sqlite_fts5_trigram"] = True
    except sqlite3.Error:
        checks["sqlite_fts5_trigram"] = False
    checks["python_3_11_or_newer"] = sys.version_info >= (3, 11)

    ok = all(checks.values())
    _print({
        "version": __version__,
        "ok": ok,
        "checks": checks,
        "data_dir": str(data_dir),
        "note": "offline environment check; does not verify Sina reachability",
    })
    return 0 if ok else 1


def _atomic_jsonl(path: Path, items: list[NewsArticle], force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite {path}; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as handle:
            tmp_path = Path(handle.name)
            for item in items:
                handle.write(item.model_dump_json() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if not force and path.exists():
            raise FileExistsError(f"refusing to overwrite {path}; pass --force")
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def _collect(args: argparse.Namespace) -> int:
    if args.output and Path(args.output).exists() and not args.force:
        raise FileExistsError("output exists; use --force to replace")
    articles = fetch_latest(args.category, args.limit)
    if args.output:
        _atomic_jsonl(Path(args.output), articles, args.force)
        _print({"ok": True, "count": len(articles), "output": args.output})
    else:
        for article in articles:
            print(article.model_dump_json())
    return 0


def _inspect(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as file:
        rows = deque((line for line in file if line.strip()), maxlen=args.limit)
    articles = [NewsArticle.model_validate_json(row) for row in rows]
    _print({"ok": True, "count": len(articles), "items": [
        {"uid": a.uid, "published_at": a.published_at.isoformat()
         if a.published_at else None, "text": a.content_text[:120]}
        for a in articles
    ]})
    return 0


def _test_fixtures(args: argparse.Namespace) -> int:
    path = Path(args.path)
    articles = parse_feed(
        parse_payload(path.read_text(encoding="utf-8")),
        datetime(2026, 3, 3, tzinfo=timezone.utc),
    )
    if not articles:
        raise ValueError("fixture contains no news; expected a populated golden fixture")
    _print({"ok": True, "count": len(articles), "first_uid": articles[0].uid})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="news24")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="run local, offline readiness checks")
    doctor.add_argument("--json", action="store_true", help="JSON output (default)")
    doctor.set_defaults(func=_doctor)

    collect = subparsers.add_parser("collect", help="fetch at most one live feed page")
    collect.add_argument("--source", choices=["sina"], default="sina")
    collect.add_argument("--category", default="all")
    collect.add_argument("--limit", type=int, default=20)
    collect.add_argument("--output", help="optional JSONL output path")
    collect.add_argument("--force", action="store_true", help="replace existing output")
    collect.set_defaults(func=_collect)

    inspect = subparsers.add_parser("inspect", help="inspect saved canonical JSONL")
    inspect.add_argument("path")
    inspect.add_argument("--limit", type=int, default=20)
    inspect.set_defaults(func=_inspect)

    fixtures = subparsers.add_parser("test-fixtures", help="validate a Sina response fixture")
    fixtures.add_argument("path")
    fixtures.set_defaults(func=_test_fixtures)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "limit", 1) < 1:
        parser.error("--limit must be positive")
    try:
        return int(args.func(args))
    except (OSError, ValueError, RuntimeError, News24Error) as exc:
        print(f"news24: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
