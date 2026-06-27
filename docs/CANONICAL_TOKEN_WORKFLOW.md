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
description, and keyword fields. It writes ranked counts and source-record examples
under `exports/boomone_mining/`. These files are evidence for review; they never
modify candidates or the canonical table.

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
