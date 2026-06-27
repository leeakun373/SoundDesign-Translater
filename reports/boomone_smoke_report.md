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
- retained unique top tokens: 41
- retained top 2/3-grams: 70
- filtered occurrences: 98

Generated files:

```text
top_tokens.csv
top_phrases.csv
token_examples.csv
phrase_examples.csv
description_examples.csv
```

Top token examples:

| token | record_count | field_hit_count |
| --- | ---: | ---: |
| heavy | 4 | 5 |
| door | 2 | 8 |
| metal | 2 | 7 |
| slam | 2 | 5 |
| wood | 2 | 8 |
| clink | 1 | 4 |
| creak | 1 | 4 |
| knock | 1 | 4 |

Top phrase examples:

| phrase | record_count | field_hit_count | n |
| --- | ---: | ---: | ---: |
| heavy metal | 2 | 2 | 2 |
| body punch | 1 | 3 | 2 |
| body punch hit | 1 | 3 | 3 |
| chain drop | 1 | 4 | 2 |
| door knock | 1 | 4 | 2 |
| engine rattle | 1 | 4 | 2 |
| metal door slam | 1 | 4 | 3 |

Filtered occurrence counts:

| reason | count | examples |
| --- | ---: | --- |
| file extension | 24 | wav, mp3, aif, aiff |
| microphone model | 11 | mkh8040, co100k |
| pure numeric | 12 | 002, 007, 416 |
| sample rate / bit depth | 4 | 96k, 192k, 24bit, 32bit |
| channel / format | 7 | mono, stereo, dualmono, ms, ab |
| version / render | 6 | v1, v2, final, premix, master, edit |
| take/index marker | 24 | take, take01, idx03, index05 |
| single letter | 1 | z |

`416` is filtered as numeric. All microphone values remain visible in the
`microphone` column of example exports and SQLite; none becomes a canonical action
candidate.

## Candidate generation v0.1

Candidate generation was invoked explicitly against a temporary file named
`canonical_token_candidates.csv` with minimum distinct record count 1 for fixture
coverage only. Production defaults remain 2.

- generated review candidates: 39
- source values: only `boom_mined`
- review status values: only `review`
- priority values: only `0`
- sample candidates: `knock`, `door knock`, `gravel scrape`, `metal door slam`

Rules admit known single action terms and filtered 2/3-grams with exactly one known
action as the final token. Broad actions such as `hit` and `drop` are marked high
ambiguity. Every row carries record and field-hit counts in `note`.

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
- `record_count` is de-duplicated, but candidate quality still depends on the selected
  minimum distinct-record threshold and source diversity.
- The action vocabulary is intentionally small and English-only; it will miss valid
  actions rather than classify unknown terms automatically.
- The XLSX reader is a lightweight OOXML reader and does not handle every merged-cell
  or formula-only workbook layout.
