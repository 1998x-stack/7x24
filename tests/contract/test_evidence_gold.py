"""Golden examples only establish exact source-span grounding."""

import json
from pathlib import Path

from news24.intelligence.service import _evidence_status

DATA = Path(__file__).parents[1] / "fixtures" / "intelligence" / "evidence_gold.json"


def test_evidence_gold_corpus() -> None:
    fixture = json.loads(DATA.read_text(encoding="utf-8"))
    assert fixture["version"] == "v1"
    cases = fixture["cases"]
    assert len(cases) >= 7
    for case in cases:
        verdict, start, end = _evidence_status(case["text"], case["quote"])
        assert verdict == case["verdict"], case
        if verdict == "TEXT_MATCH_ONLY":
            assert start is not None and end is not None
            assert case["text"][start:end] == case["quote"]
        else:
            assert start is None and end is None
