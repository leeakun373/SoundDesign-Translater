# BOOM Evidence QA Report

- total evidence rows: `1000`
- approved_for_ai count: `7`
- rejected_for_ai count: `993`
- canonical_tokens.csv changed: `no`

## Field quality distribution

- high: `4`
- medium: `463`
- low: `533`

## Example quality distribution

- high: `12`
- medium: `144`
- low: `844`

## Category alignment distribution

- aligned: `112`
- mixed: `113`
- weak: `775`
- unknown: `0`

## High-risk token decisions

- hit: approved_for_ai=no; reason=ambiguous_token;category_mixed;generic_description_hit; field_quality=medium; category_alignment=mixed
- shot: approved_for_ai=no; reason=ambiguous_token;duplicate_examples;insufficient_unique_examples; field_quality=high; category_alignment=aligned
- gun: approved_for_ai=no; reason=ambiguous_token;duplicate_examples;insufficient_unique_examples;tool_gun_context; field_quality=medium; category_alignment=aligned
- ring: approved_for_ai=no; reason=ambiguous_token;category_mixed;ambience_ring; field_quality=medium; category_alignment=mixed

## Top approved examples

- `metal`: field=medium, example=medium, category=mixed, flags=category_mixed
- `plastic`: field=medium, example=medium, category=mixed, flags=category_mixed
- `leather`: field=medium, example=medium, category=mixed, flags=category_mixed;duplicate_examples
- `glass`: field=medium, example=medium, category=mixed, flags=category_mixed
- `rubber`: field=medium, example=medium, category=mixed, flags=category_mixed
- `dirt`: field=medium, example=medium, category=mixed, flags=category_mixed;duplicate_examples
- `single shot`: field=high, example=high, category=aligned, flags=ambiguous_token;duplicate_examples

## Top blocked examples

- `impact`: field=medium, example=low, category=mixed, flags=category_mixed;duplicate_examples;insufficient_unique_examples
- `gun shot`: field=medium, example=low, category=aligned, flags=ambiguous_token;duplicate_examples;insufficient_unique_examples;shotgun_microphone
- `projectile gun shot`: field=medium, example=low, category=aligned, flags=ambiguous_token;duplicate_examples;insufficient_unique_examples;shotgun_microphone
- `wood`: field=medium, example=low, category=mixed, flags=category_mixed
- `gun`: field=medium, example=low, category=aligned, flags=ambiguous_token;duplicate_examples;insufficient_unique_examples;tool_gun_context
- `whoosh`: field=medium, example=medium, category=mixed, flags=category_mixed;duplicate_examples;existing_conflict
- `car`: field=medium, example=low, category=aligned, flags=existing_conflict
- `hit`: field=medium, example=low, category=mixed, flags=ambiguous_token;category_mixed;generic_description_hit
- `shot`: field=high, example=low, category=aligned, flags=ambiguous_token;duplicate_examples;insufficient_unique_examples
- `cannon`: field=medium, example=medium, category=mixed, flags=category_mixed;duplicate_examples;existing_conflict

## Canonical token guard

- canonical_tokens_sha256_before: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
- canonical_tokens_sha256_after: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
- canonical_tokens.csv changed: `no`
- AI invoked: `no`
- automatic promotion: `no`
