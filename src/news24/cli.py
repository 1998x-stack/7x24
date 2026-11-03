"""Public CLI compatibility facade; python -m news24 and news24 remain stable."""

from news24.interfaces.cli import _atomic_jsonl as _atomic_jsonl
from news24.interfaces.cli import build_parser, main

__all__ = ["build_parser", "main", "_atomic_jsonl"]
