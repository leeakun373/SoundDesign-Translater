# AI Prompt Candidate Review

Deterministic machine review before AI alias prompt execution.

- total approved_for_ai: `20`
- reviewed prompt-pack items: `17`
- allow_prompt: `8`
- alias_only: `9`
- block: `0`
- AI invoked: `no`
- promote: `no`
- canonical_tokens.csv changed: `no`

## new_candidate conclusions

- **Gun** (token/object): risk=`high`, recommendation=`alias_only`; cannon_long_gun_context;not_for_new_candidate
- **Hit** (token/action): risk=`high`, recommendation=`allow_prompt`; ambiguous_with_impact;ambiguous_with_knock;ambiguous_with_punch;forbid_visual_alias_命中
- **Squeak** (token/action): risk=`high`, recommendation=`allow_prompt`; guns_category_with_metal_squeak_fxname;toy_cartoon_metal_friction_squeak
- **Crack** (token/action): risk=`medium`, recommendation=`allow_prompt`; broad_material_spread;forbid_visual_alias_裂纹
- **Single Shot** (phrase/action): risk=`medium`, recommendation=`allow_prompt`; phrase_candidate;keep_phrase_do_not_split

## alias_expansion conclusions

- **Impact** (token/action): risk=`low`, recommendation=`alias_only`; existing_keep
- **Friction** (token/action): risk=`low`, recommendation=`alias_only`; existing_keep
- **Gun** (token/object): risk=`high`, recommendation=`alias_only`; cannon_long_gun_context
- **Hit** (token/action): risk=`high`, recommendation=`allow_prompt`; ambiguous_with_impact;ambiguous_with_knock;ambiguous_with_punch;forbid_visual_alias_命中
- **Squeak** (token/action): risk=`high`, recommendation=`allow_prompt`; guns_category_with_metal_squeak_fxname;toy_cartoon_metal_friction_squeak
- **Shot** (token/action): risk=`medium`, recommendation=`alias_only`; existing_keep;synthetic_processed_shot
- **Chain** (token/object): risk=`low`, recommendation=`alias_only`; existing_keep
- **Crack** (token/action): risk=`medium`, recommendation=`allow_prompt`; broad_material_spread;forbid_visual_alias_裂纹
- **Door** (token/object): risk=`medium`, recommendation=`alias_only`; existing_keep
- **Drop** (token/action): risk=`medium`, recommendation=`alias_only`; existing_keep
- **Ring** (token/action): risk=`medium`, recommendation=`alias_only`; existing_keep;musical_percussion_ringing;not_for_new_candidate
- **Single Shot** (phrase/action): risk=`medium`, recommendation=`allow_prompt`; phrase_candidate;keep_phrase_do_not_split

## Downgraded items

- `new_candidate` **Gun**: recommendation=`alias_only`, risk=`high`; cannon_long_gun_context;not_for_new_candidate
- `alias_expansion` **Impact**: recommendation=`alias_only`, risk=`low`; existing_keep
- `alias_expansion` **Friction**: recommendation=`alias_only`, risk=`low`; existing_keep
- `alias_expansion` **Gun**: recommendation=`alias_only`, risk=`high`; cannon_long_gun_context
- `alias_expansion` **Shot**: recommendation=`alias_only`, risk=`medium`; existing_keep;synthetic_processed_shot
- `alias_expansion` **Chain**: recommendation=`alias_only`, risk=`low`; existing_keep
- `alias_expansion` **Door**: recommendation=`alias_only`, risk=`medium`; existing_keep
- `alias_expansion` **Drop**: recommendation=`alias_only`, risk=`medium`; existing_keep
- `alias_expansion` **Ring**: recommendation=`alias_only`, risk=`medium`; existing_keep;musical_percussion_ringing;not_for_new_candidate

## Best to keep

- `new_candidate` **Hit**: recommendation=`allow_prompt`, risk=`high`; ambiguous_with_impact;ambiguous_with_knock;ambiguous_with_punch;forbid_visual_alias_命中
- `new_candidate` **Squeak**: recommendation=`allow_prompt`, risk=`high`; guns_category_with_metal_squeak_fxname;toy_cartoon_metal_friction_squeak
- `new_candidate` **Crack**: recommendation=`allow_prompt`, risk=`medium`; broad_material_spread;forbid_visual_alias_裂纹
- `new_candidate` **Single Shot**: recommendation=`allow_prompt`, risk=`medium`; phrase_candidate;keep_phrase_do_not_split
- `alias_expansion` **Hit**: recommendation=`allow_prompt`, risk=`high`; ambiguous_with_impact;ambiguous_with_knock;ambiguous_with_punch;forbid_visual_alias_命中
- `alias_expansion` **Squeak**: recommendation=`allow_prompt`, risk=`high`; guns_category_with_metal_squeak_fxname;toy_cartoon_metal_friction_squeak
- `alias_expansion` **Crack**: recommendation=`allow_prompt`, risk=`medium`; broad_material_spread;forbid_visual_alias_裂纹
- `alias_expansion` **Single Shot**: recommendation=`allow_prompt`, risk=`medium`; phrase_candidate;keep_phrase_do_not_split

## Most dangerous

- `new_candidate` **Squeak**: recommendation=`allow_prompt`, risk=`high`; guns_category_with_metal_squeak_fxname;toy_cartoon_metal_friction_squeak
- `alias_expansion` **Squeak**: recommendation=`allow_prompt`, risk=`high`; guns_category_with_metal_squeak_fxname;toy_cartoon_metal_friction_squeak
- `new_candidate` **Hit**: recommendation=`allow_prompt`, risk=`high`; ambiguous_with_impact;ambiguous_with_knock;ambiguous_with_punch;forbid_visual_alias_命中
- `alias_expansion` **Hit**: recommendation=`allow_prompt`, risk=`high`; ambiguous_with_impact;ambiguous_with_knock;ambiguous_with_punch;forbid_visual_alias_命中
- `new_candidate` **Gun**: recommendation=`alias_only`, risk=`high`; cannon_long_gun_context;not_for_new_candidate
- `alias_expansion` **Gun**: recommendation=`alias_only`, risk=`high`; cannon_long_gun_context

## Inputs

- `E:\WorkSpace\SoundDesign Translater\exports\boomone_candidates\candidate_evidence.csv`
- `E:\WorkSpace\SoundDesign Translater\exports\boomone_candidates\expanded_examples.csv`
- `E:\WorkSpace\SoundDesign Translater\exports\ai_alias_prompt_pack\new_candidate\alias_prompt_items.jsonl`
- `E:\WorkSpace\SoundDesign Translater\exports\ai_alias_prompt_pack\alias_expansion\alias_prompt_items.jsonl`

## Canonical token guard

- canonical_tokens_sha256: `4B5F4675861C226E956BD35DFE307678AC274EB1A61064DB8262D8D5659EFE3E`
- canonical path: `E:\WorkSpace\SoundDesign Translater\fxengine\data\canonical_tokens.csv`
