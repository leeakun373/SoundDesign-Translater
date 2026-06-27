# Canonical Token Data

`canonical_tokens.csv` is the versioned, UTF-8 source of truth for FXName canonical aliases.

Schema:

- `raw`: input alias.
- `canonical`: canonical English FXName token or token group.
- `slot`: one of `material`, `object`, `source`, `action`, `motion`, `detail`, or `modifier`.
- `lang`: input language (`zh` or `en`).
- `priority`: tie-breaker for duplicate aliases; higher wins.
- `tags`: slash-separated review/search labels.
- `note`: optional maintenance note.

Lookup precedence is Personal Dictionary, this CSV, then the existing glossary. Chinese matching is longest-alias first, with priority used as the tie-breaker. Keep aliases in this file rather than adding Python `if`/`else` mappings.

Run the read-only quality audit after editing:

```powershell
python -m fxengine.canonical_audit
```

The command prints structured JSON and exits non-zero when it finds duplicate aliases, conflicting mappings, invalid fields, malformed tags, or duplicate rows. It never edits the CSV.
