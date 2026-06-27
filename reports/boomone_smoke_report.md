# BOOM Corpus Smoke Test + Candidate Generation v0.1

Date: 2026-06-28

## Scope and fixture

The smoke input is `tests/fixtures/boomone_sample_metadata.csv`: 12 entirely
synthetic BOOM-style rows. It contains no copied BOOM descriptions or other real
copyright metadata.

One sparse table exercises these header aliases:

- filename: `Filename`, `File Name`, `filename`
- FX name: `FXName`, `FX Name`, `Title`
- description: `Description`, `Desc`
- classification: `Category`, `SubCategory`, `CatID`
- evidence metadata: `Keywords`, `Microphone`

When multiple aliases for one logical field exist, export uses the first populated
value from left to right.

## Export smoke result

- source files: 1
- source sheets/tables: 1
- exported records: 12
- skipped rows: 0
- warnings: 0
- repeated export: identical SQLite row order/content and identical grouped CSV
  hashes

SQLite table `boomone_records`:

```text
record_id
library
filename
fx_name
description
cat_id
category
subcategory
category_full
vendor_category
keywords
microphone
source_file
```

All fields except the optional `vendor_category` were populated in all 12 rows.

## Mining smoke result

- records: 12
- retained unique top tokens: 39
- retained top 2/3-grams: 64
- filtered occurrences: 58

Generated files:

```text
top_tokens.csv
top_phrases.csv
token_examples.csv
phrase_examples.csv
description_examples.csv
```

Top token examples:

| token | count | record_count |
| --- | ---: | ---: |
| door | 6 | 2 |
| metal | 6 | 2 |
| wood | 6 | 2 |
| heavy | 5 | 4 |
| clink | 3 | 1 |
| creak | 3 | 1 |
| impact | 3 | 1 |
| knock | 3 | 1 |

Top phrase examples:

| phrase | count | record_count | n |
| --- | ---: | ---: | ---: |
| body punch | 3 | 1 | 2 |
| body punch hit | 3 | 1 | 3 |
| chain drop | 3 | 1 | 2 |
| door knock | 3 | 1 | 2 |
| engine rattle | 3 | 1 | 2 |
| gravel scrape | 3 | 1 | 2 |
| metal door slam | 3 | 1 | 3 |

Filtered occurrence counts:

| reason | count | examples |
| --- | ---: | --- |
| file extension | 12 | wav, mp3, aif, aiff |
| microphone model | 11 | mkh8040, co100k |
| pure numeric | 6 | 002, 007, 416 |
| stop/metadata boilerplate | 11 | recorded, mono, stereo |
| take/index marker | 18 | take, take01, idx03, index05 |

`416` is filtered as numeric. All microphone values remain visible in the
`microphone` column of example exports and SQLite; none becomes a canonical action
candidate.

## Candidate generation v0.1

Candidate generation was invoked explicitly against a temporary file named
`canonical_token_candidates.csv` with minimum occurrence count 2.

- generated review candidates: 30
- ambiguity medium: 24
- ambiguity high: 6
- source values: only `boom_mined`
- review status values: only `review`
- priority values: only `0`
- sample candidates: `knock`, `door knock`, `gravel scrape`, `metal door slam`

Rules admit known single action terms and filtered 2/3-grams with exactly one known
action as the final token. Broad actions such as `hit` and `drop` are marked high
ambiguity. Every row carries occurrence and record counts in `note`.

The repository `fxengine/data/canonical_token_candidates.csv` was not populated from
this synthetic fixture. The smoke used a temporary candidate file.

## Safety boundary

- `canonical_tokens.csv` SHA-256 before and after smoke:
  `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
- wrote to `canonical_tokens.csv`: **no**
- automatic promotion: **no**
- BOOM/AI final normalize override: **no**

## Known risks

- Header aliases remain heuristic; unfamiliar vendor columns require new aliases.
- Occurrence count can repeat within FXName/description/keywords from one record.
  `record_count` is included for review, but v0.1 does not enforce a minimum distinct
  record count.
- The action vocabulary is intentionally small and English-only; it will miss valid
  actions rather than classify unknown terms automatically.
- The XLSX reader is a lightweight OOXML reader and does not handle every merged-cell
  or formula-only workbook layout.
