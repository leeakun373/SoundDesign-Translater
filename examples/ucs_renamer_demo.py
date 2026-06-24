#!/usr/bin/env python3
"""UCSRenamer HTTP-only preview draft integration example."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from client.python.client import LocalTranslateClient


@dataclass(frozen=True)
class RenamePreviewDraft:
    original_name: str
    translated_preview: str
    user_draft: str
    debug: dict


def build_preview_draft(
    source_name: str, base_url: str = "http://127.0.0.1:18765"
) -> RenamePreviewDraft:
    """Call LocalTranslate and prepare editable preview text; never rename here."""
    client = LocalTranslateClient(base_url)
    health = client.health()
    if not health.get("model_ready"):
        raise RuntimeError("LocalTranslate is not ready. Start it with: python service/server.py")

    result = client.translate(source_name, mode="auto", pro_mode=True)
    return RenamePreviewDraft(
        original_name=source_name,
        translated_preview=result.translation,
        user_draft=result.translation,
        debug=result.debug,
    )


def main() -> None:
    sample = "木门 滑开"
    if len(sys.argv) > 1:
        sample = " ".join(sys.argv[1:])

    draft = build_preview_draft(sample)
    print("=== UCSRenamer preview draft ===")
    print("original :", draft.original_name)
    print("preview  :", draft.translated_preview)
    print("draft    :", draft.user_draft)
    print("debug    :", draft.debug)
    print("rename   : not performed")


if __name__ == "__main__":
    main()
