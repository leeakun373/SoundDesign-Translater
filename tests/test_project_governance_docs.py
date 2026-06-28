"""Lightweight checks that project governance docs exist and cover key invariants."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


@pytest.mark.parametrize(
    "relative_path",
    [
        "docs/PROJECT_INVARIANTS.md",
        "docs/AI_ALIAS_WORKFLOW.md",
        "docs/AI_ALIAS_REVIEW_RULES.md",
        "docs/LOCAL_AI_AGENT_PLAYBOOK.md",
        "docs/BATCH_PROMOTION_PLAN.md",
        "AGENTS.md",
    ],
)
def test_governance_doc_exists(relative_path: str) -> None:
    path = ROOT / relative_path
    assert path.is_file(), f"missing governance doc: {relative_path}"


def test_project_invariants_covers_runtime_guards() -> None:
    text = (DOCS / "PROJECT_INVARIANTS.md").read_text(encoding="utf-8")
    for keyword in (
        "canonical_tokens.csv",
        "review_status=keep",
        "ai_candidate",
        "promote",
        "hash guard",
        "AI invoked",
    ):
        assert keyword in text, f"PROJECT_INVARIANTS.md missing: {keyword}"


def test_ai_alias_workflow_covers_pipeline_artifacts() -> None:
    text = (DOCS / "AI_ALIAS_WORKFLOW.md").read_text(encoding="utf-8")
    for keyword in (
        "reviewed_new_candidate",
        "ai_alias_candidates_review_real.csv",
        "decision_recommendation",
        "build_boom_candidate_evidence.py",
        "import_ai_alias_candidates.py",
    ):
        assert keyword in text, f"AI_ALIAS_WORKFLOW.md missing: {keyword}"


def test_ai_alias_review_rules_covers_special_canonicals() -> None:
    text = (DOCS / "AI_ALIAS_REVIEW_RULES.md").read_text(encoding="utf-8")
    for keyword in (
        "Hit",
        "Crack",
        "Shot",
        "Gun",
        "Single Shot",
        "batch_safe",
        "batch_weapon",
        "conflict_group",
    ):
        assert keyword in text, f"AI_ALIAS_REVIEW_RULES.md missing: {keyword}"


def test_local_ai_agent_playbook_covers_session_checklist() -> None:
    text = (DOCS / "LOCAL_AI_AGENT_PLAYBOOK.md").read_text(encoding="utf-8")
    for keyword in (
        "pytest",
        "git status",
        "canonical_tokens.csv changed",
        "PROJECT_INVARIANTS.md",
    ):
        assert keyword in text, f"LOCAL_AI_AGENT_PLAYBOOK.md missing: {keyword}"


def test_agents_md_points_to_core_docs() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for keyword in (
        "docs/PROJECT_INVARIANTS.md",
        "docs/AI_ALIAS_WORKFLOW.md",
        "docs/AI_ALIAS_REVIEW_RULES.md",
        "canonical_tokens.csv",
        "pytest",
    ):
        assert keyword in text, f"AGENTS.md missing: {keyword}"
