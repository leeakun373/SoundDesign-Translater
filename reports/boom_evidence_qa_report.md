# BOOM Evidence QA Report

- total evidence rows: `1000`
- expanded evidence rows: `13617`
- approved_for_ai before expansion: `7`
- approved_for_ai count: `20`
- rejected_for_ai count: `980`
- canonical_tokens.csv changed: `no`

## Field quality distribution

- high: `42`
- medium: `388`
- low: `570`

## Example quality distribution

- high: `405`
- medium: `20`
- low: `575`

## Category alignment distribution

- aligned: `107`
- mixed: `27`
- weak: `555`
- unknown: `311`

## High-risk token decisions

- hit: approved_for_ai=yes; reason=ambiguous_token; field_quality=high; category_alignment=aligned
- shot: approved_for_ai=yes; reason=ambiguous_token;duplicate_examples; field_quality=high; category_alignment=aligned
- gun: approved_for_ai=yes; reason=ambiguous_token;duplicate_examples; field_quality=high; category_alignment=aligned
- ring: approved_for_ai=yes; reason=ambiguous_token; field_quality=high; category_alignment=aligned
- whoosh: approved_for_ai=no; reason=existing_conflict; field_quality=high; category_alignment=aligned

## Top approved examples

- `metal`: field=high, example=high, category=aligned, flags=duplicate_examples
- `impact`: field=high, example=high, category=aligned, flags=none
- `wood`: field=high, example=high, category=aligned, flags=none
- `gun`: field=high, example=high, category=aligned, flags=ambiguous_token;duplicate_examples
- `hit`: field=high, example=high, category=aligned, flags=ambiguous_token
- `shot`: field=high, example=high, category=aligned, flags=ambiguous_token;duplicate_examples
- `plastic`: field=high, example=high, category=aligned, flags=none
- `leather`: field=high, example=high, category=aligned, flags=none
- `friction`: field=high, example=high, category=aligned, flags=none
- `cloth`: field=high, example=high, category=aligned, flags=duplicate_examples

## Top blocked examples

- `gun shot`: field=medium, example=high, category=weak, flags=ambiguous_token;category_mismatch
- `projectile gun shot`: field=low, example=low, category=unknown, flags=ambiguous_token;category_unknown;insufficient_unique_examples
- `whoosh`: field=high, example=high, category=aligned, flags=existing_conflict
- `car`: field=medium, example=high, category=weak, flags=category_mismatch;existing_conflict
- `cannon`: field=high, example=high, category=aligned, flags=duplicate_examples;existing_conflict
- `rubber`: field=medium, example=high, category=weak, flags=category_mismatch
- `scrape`: field=medium, example=high, category=weak, flags=category_mismatch
- `hard hit`: field=medium, example=high, category=aligned, flags=ambiguous_token
- `tonal`: field=medium, example=high, category=mixed, flags=ambiguous_token;category_mixed;detail_modifier
- `rattle`: field=medium, example=high, category=weak, flags=category_mismatch

## Canonical token guard

- canonical_tokens_sha256_before: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
- canonical_tokens_sha256_after: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
- canonical_tokens.csv changed: `no`
- AI invoked: `no`
- automatic promotion: `no`
