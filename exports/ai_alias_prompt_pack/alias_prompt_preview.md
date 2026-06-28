# AI Alias Prompt Preview

This file is a local input preview. No AI service was called.

## Required output format

```csv
raw,canonical,slot,lang,priority,rule_type,review_status,ambiguity,tags,source,note
```

Output constraints:

- `review_status` must be `review`.
- `source` must be `ai_candidate`.
- `priority` must be `0`.
- Never output `keep`.
- Do not output free-translation sentences or metadata descriptions.
- Do not overwrite `canonical_tokens.csv`.

## Item 1: Single Shot

- canonical: `Single Shot`
- slot: `action`
- candidate_type: `phrase`
- record_count: `875`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"","description":"Trigger is flicked producing a short click. Gun is empty and silencer is engaged.","category":"GUNS/MECHANISM","cat_id":""}
  - {"fx_name":"","description":"Trigger is flicked producing a short, sharp impact. Gun is empty but silencer is not engaged.","category":"GUNS/MECHANISM","cat_id":""}
