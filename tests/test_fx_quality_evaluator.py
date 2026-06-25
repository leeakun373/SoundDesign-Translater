#!/usr/bin/env python3
"""Unit tests for FXName quality evaluator (bad phrase gate + heuristics)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from glossary.fx_quality import evaluate_fx_output, find_bad_phrases, normalize_fx_issue


def test_absolute_bad_phrases_fail() -> None:
    cases = [
        ("Plastic Box Get Out Of Here It S Down", ["get out of here", "it s"]),
        ("Metal Door Was Knocked Knock", ["was knocked"]),
        ("Cloth Pull Oh My God Moving", ["oh my god"]),
        ("How Can I Help You", ["how can i help you", "you"]),
    ]
    for output, expected_substrings in cases:
        result = evaluate_fx_output("test", output)
        assert result.quality == "fail", f"{output!r} should fail, got {result.quality}"
        assert "bad_phrase" in result.issues
        for sub in expected_substrings:
            assert any(sub in p for p in result.matched_bad_phrases), (
                f"{output!r}: expected {sub!r} in {result.matched_bad_phrases}"
            )


def test_pronoun_fail() -> None:
    result = evaluate_fx_output("门", "You Open Door")
    assert result.quality == "fail"
    assert "bad_phrase" in result.issues


def test_clean_output_pass() -> None:
    result = evaluate_fx_output("木门滑开", "Wood Door Slide")
    assert result.quality == "pass"
    assert not result.issues


def test_empty_output_fail() -> None:
    result = evaluate_fx_output("木门滑开", "")
    assert result.quality == "fail"
    assert "empty_output" in result.issues


def test_too_long_needs_review() -> None:
    long_out = "One Two Three Four Five Six Seven Nine Ten"
    result = evaluate_fx_output("长描述", long_out)
    assert result.quality == "needs_review"
    assert "too_long" in result.issues


def test_duplicate_token_needs_review() -> None:
    result = evaluate_fx_output("敲门", "Door Door Knock")
    assert result.quality == "needs_review"
    assert "duplicate_token" in result.issues


def test_issue_name_normalization() -> None:
    assert normalize_fx_issue("natural_sentence") == "sentence_like_output"
    assert normalize_fx_issue("nllb_rejected") == "nllb_candidate_rejected"
    assert normalize_fx_issue("rejected_nllb_candidate:foo") == "nllb_candidate_rejected"
    assert normalize_fx_issue("low_information") is None
    assert normalize_fx_issue("missing:Door") is None


def test_find_bad_phrases() -> None:
    abs_hits, risk_hits = find_bad_phrases("Water Flow Stone It S Over")
    assert "it s" in abs_hits
    assert "is" in risk_hits or "it s" in abs_hits


def main() -> int:
    tests = [
        test_absolute_bad_phrases_fail,
        test_pronoun_fail,
        test_clean_output_pass,
        test_empty_output_fail,
        test_too_long_needs_review,
        test_duplicate_token_needs_review,
        test_issue_name_normalization,
        test_find_bad_phrases,
    ]
    failures: list[str] = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failures.append(f"{fn.__name__}: {exc}")
    if failures:
        print("FX quality evaluator failures:")
        for f in failures:
            print("-", f)
        return 1
    print(f"FX quality evaluator PASS ({len(tests)} tests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
