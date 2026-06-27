# Canonical Token Data

`canonical_tokens.csv` is the versioned, UTF-8 source of truth for FXName canonical aliases.

Schema:

- `raw`: input alias.
- `canonical`: canonical English FXName token or token group; may be empty only for `review`/`reject`.
- `slot`: one of `action`, `material`, `object`, `source`, `motion`, `detail`, `modifier`, or `unknown`.
- `lang`: input language (`zh`, `en`, `mixed`, or `pinyin`).
- `priority`: tie-breaker for duplicate aliases; higher wins.
- `rule_type`: phrase/single-token confidence and ambiguity policy.
- `review_status`: `keep`, `review`, or `reject`; only `keep` is available at runtime.
- `ambiguity`: `low`, `medium`, or `high`.
- `tags`: lowercase slash format (`impact/heavy`); each segment may contain lowercase letters, digits, `_`, or `-`.
- `source`: `manual`, `ai_candidate`, `ai_reviewed`, `boom_mined`, or `glossary_seed`.
- `note`: optional maintenance note.

Lookup precedence is Personal Dictionary, this CSV, then the existing glossary. Chinese matching is longest-alias first, with priority used as the tie-breaker. Keep aliases in this file rather than adding Python `if`/`else` mappings.

Legacy seven-column CSV files remain readable. Missing governance fields are inferred
as `keep`, phrase/stable-single, `low`, and `manual`. New table edits must use the full
11-column schema.

Run the read-only quality audit after editing:

```powershell
python -m fxengine.canonical_audit
```

The command prints structured JSON, writes the audit report/conflict CSV, and exits
non-zero on errors. Policy warnings are reported without failing the command. It never
edits `canonical_tokens.csv`.

See `docs/CANONICAL_TOKEN_WORKFLOW.md` for BOOM mining, candidate review, and explicit
promotion.
