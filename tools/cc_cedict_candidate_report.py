#!/usr/bin/env python3
"""CLI for the CC-CEDICT offline *weak candidate* layer (v0.1).

This tool is **review-only**. It never writes ``canonical_tokens.csv`` and is not
wired into Normalize. It only prints a proposal for a single token (or a batch
CSV) so a human / BOOM Mining flow can decide whether to promote.

Example::

    python tools/cc_cedict_candidate_report.py \
        --token 衣柜 --target "Heavy Wood Wardrobe Slide Slow Creak"
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from glossary.cc_cedict import CEDictIndex  # noqa: E402


def _serialise(result: dict) -> dict:
    """Convert ``propose_for_target`` output into plain JSON-able dicts."""

    out = dict(result)
    out["candidates"] = [asdict(c) for c in result.get("candidates", [])]
    return out


def _render_markdown(result: dict) -> str:
    lines = [
        f"# CC-CEDICT candidate report",
        "",
        f"- token: `{result['token']}`",
        f"- target: `{result['target']}`",
        f"- status: **{result['status']}**",
        f"- reasons: {', '.join(result['reasons']) or '(none)'}",
        "",
        "## candidates",
        "",
    ]
    candidates = result.get("candidates", [])
    if not candidates:
        lines.append("(none)")
    else:
        lines.append("| canonical | confidence | reason | gloss |")
        lines.append("|-----------|-----------|--------|-------|")
        for c in candidates:
            lines.append(
                f"| {c['canonical']} | {c['confidence']} | {c['reason']} | {c['gloss']} |"
            )
    return "\n".join(lines)


def _run_single(index: CEDictIndex, token: str, target: str, fmt: str) -> None:
    result = _serialise(index.propose_for_target(token, target))
    if fmt == "markdown":
        print(_render_markdown(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def _run_batch(index: CEDictIndex, csv_path: Path, fmt: str) -> None:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        results = []
        for row in reader:
            token = (row.get("token") or "").strip()
            target = (row.get("target") or "").strip()
            if not token:
                continue
            results.append(_serialise(index.propose_for_target(token, target)))
    if fmt == "markdown":
        print("\n\n---\n\n".join(_render_markdown(r) for r in results))
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Offline CC-CEDICT weak candidate report (review-only; never writes "
            "canonical_tokens.csv)."
        )
    )
    parser.add_argument("--token", help="Simplified Chinese token to look up.")
    parser.add_argument(
        "--target",
        default="",
        help="BOOM target FXName used for case-insensitive word support check.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Optional batch CSV with 'token' and 'target' columns.",
    )
    parser.add_argument(
        "--cedict",
        type=Path,
        default=None,
        help="Path to a CC-CEDICT .u8 file (defaults to the bundled snapshot).",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format (default: json).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.token and not args.csv:
        parser.error("provide --token (single) or --csv (batch)")

    index = CEDictIndex.from_file(args.cedict)

    if args.csv:
        _run_batch(index, args.csv, args.format)
    else:
        _run_single(index, args.token, args.target, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
