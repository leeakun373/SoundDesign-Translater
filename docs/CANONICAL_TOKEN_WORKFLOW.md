# Canonical Token Workflow

Canonical tokens are governed runtime data, not a destination for unreviewed model or
metadata suggestions. The supported path is:

```text
BOOM metadata
→ corpus
→ mining exports
→ canonical candidates
→ conflict filtering
→ human review
→ promote keep rows
→ canonical_tokens.csv
→ runtime normalize only uses keep
```

## 1. Build the BOOM corpus

Keep BOOM's original metadata, CatID, Category, and SubCategory as the authority in
this phase. The exporter accepts a directory containing `.csv`, `.xlsx`, or `.xlsm`
metadata files:

```powershell
python tools/export_boomone_corpus.py "D:\BOOM metadata"
```

It produces `data/boomone/boomone_records.sqlite`, category-grouped CSV files under
`exports/boomone_by_ucs/`, and `reports/boomone_coverage.md`. It maps known columns
into a stable schema and records the source file/sheet. It does not use AI to
reclassify BOOM metadata.

## 2. Mine evidence exports

```powershell
python tools/mine_boomone_tokens.py
```

The miner deterministically counts English tokens, bigrams, and trigrams in FXName,
description, keyword, and filename fields. `record_count` counts an item at most once
per record; `field_hit_count` counts distinct record/field hits. Repetition within one
field cannot inflate either metric. Example exports retain `field_source` and
`field_value`. These files are evidence for review and never modify the canonical
table. The default mining run also leaves candidates untouched; candidate writing
requires the explicit option below.

Mining filters pure numbers, audio file extensions, take/index markers, sample rates,
bit depths, channel/format labels, version/render labels, single-letter noise,
vendor/category/library codes, common metadata boilerplate, and microphone model
tokens such as `MKH8040`, `CO100K`, and `416`. Acoustic actions such as `crack`,
`snap`, and `slam` are explicitly retained. The original microphone value remains in
SQLite and example exports as metadata.

A real-corpus quality report can be generated without candidates:

```powershell
python tools/mine_boomone_tokens.py `
  --quality-report reports/boomone_mining_quality_report.md
```

The report includes input files, record and field coverage, top tokens/phrases,
filtered metadata, suspected actions/objects, candidate status, and canonical table
SHA-256 before/after. The exporter supports CSV/XLSX/XLSM; legacy `.xls` requires a
separate conversion step and is not silently reclassified.

Candidate generation v0.1 is explicit and conservative:

```powershell
python tools/mine_boomone_tokens.py `
  --candidates fxengine/data/canonical_token_candidates.csv `
  --candidate-min-count 2
```

- The output filename must be `canonical_token_candidates.csv`; the tool refuses a
  `canonical_tokens.csv` target.
- Single-token candidates must belong to the small built-in action vocabulary.
- Phrase candidates are filtered 2-grams/3-grams containing exactly one known action
  as the final word.
- Evidence must meet the requested distinct-record threshold. `record_count` and
  `field_hit_count` are recorded in `note` for human review.
- Every generated row uses `slot=action`, `source=boom_mined`,
  `review_status=review`, `priority=0`, and `ambiguity=medium|high`.
- Candidate generation never calls promotion and never edits the runtime table.

## 3. Review candidates

Copy selected evidence into `fxengine/data/canonical_token_candidates.csv` using the
same 11-column schema as the main table. Candidate rows remain inert. Set
`review_status=keep` only after checking the mapping, slot, ambiguity, note, source,
and conflicts. `ai_candidate` and `boom_mined` identify provenance; source alone does
not grant runtime access.

Run an explicit promotion:

```powershell
python tools/promote_token_candidates.py --dry-run
python tools/promote_token_candidates.py
```

Only keep rows without a serious conflict are promoted. An existing keep row with
the same raw and a different canonical is written to
`fxengine/data/canonical_token_conflicts.csv` and is not overwritten. Promotion
preserves canonical column order. Review/reject candidates are skipped.

## 4. Audit and runtime loading

```powershell
python -m fxengine.canonical_audit
```

The audit writes `reports/canonical_token_audit.md` and
`fxengine/data/canonical_token_conflicts.csv`. Schema errors and canonical conflicts
cause a non-zero exit. Governance signals such as approved high-risk single
characters are warnings and remain visible in the report.

`CanonicalDB.token_count` counts runtime keep rows;
`CanonicalDB.raw_csv_row_count` counts every CSV row. Review/reject rows do not enter
the positive zh/ascii indexes. They suppress an identical legacy glossary fallback,
so a reviewed phrase such as `划过` remains unknown instead of becoming `Passby`.
Personal Dictionary still has higher precedence than the canonical table, and phrase
matching remains longest-first.

## Hard boundaries

- Unknown text does not go through NLLB and is not written into final FXName.
- A BOOM suggestion never overwrites final output.
- An AI candidate never enters the main table automatically.
- A BOOM-mined row never writes directly to `canonical_tokens.csv`.
- Review/reject rows never participate in final normalize.
- Loading or mining candidates never triggers promotion; promotion is an explicit
  command after human review.
