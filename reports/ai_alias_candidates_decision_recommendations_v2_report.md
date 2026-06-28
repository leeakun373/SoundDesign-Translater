# AI Alias Candidate Decision Recommendations Report

Recommendation table only. No canonical overwrite, runtime activation, keep, or promotion.

- total_count: `48`
- accept_candidate: `4`
- needs_review: `41`
- reject_candidate: `3`
- conflict_group_count: `1`
- conflict_candidate_count: `2`
- keep appears: `no`
- all_source_ai_candidate: `true`
- all_priority_zero: `true`
- canonical_tokens.csv changed: `no`
- promote: `no`
- CSV: `exports\ai_alias_prompt_pack\ai_alias_candidates_decision_recommendations_v2.csv`

## Decisions by canonical

- Chain: accept_candidate=2, needs_review=2, reject_candidate=0
- Crack: accept_candidate=0, needs_review=4, reject_candidate=0
- Door: accept_candidate=0, needs_review=4, reject_candidate=0
- Drop: accept_candidate=0, needs_review=3, reject_candidate=1
- Friction: accept_candidate=2, needs_review=1, reject_candidate=1
- Gun: accept_candidate=0, needs_review=4, reject_candidate=0
- Hit: accept_candidate=0, needs_review=3, reject_candidate=1
- Impact: accept_candidate=0, needs_review=4, reject_candidate=0
- Ring: accept_candidate=0, needs_review=4, reject_candidate=0
- Shot: accept_candidate=0, needs_review=4, reject_candidate=0
- Single Shot: accept_candidate=0, needs_review=4, reject_candidate=0
- Squeak: accept_candidate=0, needs_review=4, reject_candidate=0

## Decisions by review batch

- batch_safe: accept_candidate=4, needs_review=14, reject_candidate=2
- batch_caution: accept_candidate=0, needs_review=15, reject_candidate=1
- batch_weapon: accept_candidate=0, needs_review=12, reject_candidate=0

## Needs review

- 击打 / Hit / caution_batch_default;surface_replace_raw;ambiguous_with_impact_knock_punch
- 碰击 / Hit / caution_batch_default;surface_replace_raw;ambiguous_with_impact_knock_punch;raw_multi_canonical_conflict / raw_conflict_001
- 拳击 / Hit / caution_batch_default;fight_specific_surface;ambiguous_with_impact_knock_punch;fight_specific
- 吱吱 / Squeak / caution_batch_default;surface_replace_raw;category_pollution_possible
- 尖锐吱响 / Squeak / caution_batch_default;category_pollution_possible
- 挤压吱响 / Squeak / caution_batch_default;category_pollution_possible
- 金属吱响 / Squeak / caution_batch_default;category_pollution_possible
- 脆裂 / Crack / caution_batch_default;surface_replace_raw;broad_material_spread
- 爆裂脆响 / Crack / caution_batch_default;broad_material_spread
- 劈裂 / Crack / caution_batch_default;surface_replace_raw;broad_material_spread
- 断裂脆响 / Crack / caution_batch_default;broad_material_spread
- 单发 / Single Shot / weapon_batch_default;phrase_weapon_high_risk
- 单发射击 / Single Shot / weapon_batch_default;phrase_weapon_high_risk
- 单次开火 / Single Shot / weapon_batch_default;phrase_weapon_high_risk
- 单发枪 / Single Shot / weapon_batch_default;surface_replace_raw;phrase_weapon_high_risk
- 冲击 / Impact / safe_medium_risk;surface_replace_raw;standard_alias_review
- 重物撞击 / Impact / safe_medium_risk;surface_too_descriptive;standard_alias_review
- 碰击 / Impact / safe_medium_risk;surface_replace_raw;standard_alias_review;raw_multi_canonical_conflict / raw_conflict_001
- 砸击 / Impact / safe_medium_risk;surface_replace_raw;standard_alias_review
- 表面摩擦 / Friction / safe_low_risk;surface_too_descriptive;standard_alias_review
- 枪械 / Gun / weapon_batch_default;weapon_object_high_risk
- 枪支 / Gun / weapon_batch_default;weapon_object_high_risk
- 火器 / Gun / weapon_batch_default;weapon_object_high_risk
- 枪炮 / Gun / weapon_batch_default;weapon_object_high_risk;broad_weapon_term
- 枪声 / Shot / weapon_batch_default;weapon_action_high_risk
- 炮击 / Shot / weapon_batch_default;shot_sound_concept;weapon_action_high_risk
- 开火 / Shot / weapon_batch_default;surface_replace_raw;weapon_action_high_risk
- 发射 / Shot / weapon_batch_default;too_broad_weapon_action;weapon_action_high_risk
- 链条 / Chain / safe_low_risk;object_slot_sound_event;standard_alias_review
- 铁链晃动 / Chain / safe_low_risk;object_slot_sound_event;standard_alias_review
- 开门 / Door / safe_medium_risk;door_event_not_object;standard_alias_review
- 关门 / Door / safe_medium_risk;door_event_not_object;standard_alias_review
- 门板响 / Door / safe_medium_risk;object_slot_sound_event;standard_alias_review
- 门轴吱响 / Door / safe_medium_risk;hinge_squeak_event;standard_alias_review;object_slot_sound_event
- 坠落 / Drop / safe_medium_risk;surface_replace_raw;standard_alias_review
- 坠地 / Drop / safe_medium_risk;surface_replace_raw;standard_alias_review
- 跌落 / Drop / safe_medium_risk;surface_replace_raw;standard_alias_review
- 振铃 / Ring / caution_batch_default;tonal_ring_surface;tonal_ambience_possible
- 余响 / Ring / caution_batch_default;tonal_tail_no_auto_promote;tonal_ambience_possible;tonal_tail_or_reverb_possible
- 回响声 / Ring / caution_batch_default;tonal_tail_no_auto_promote;tonal_ambience_possible;tonal_tail_or_reverb_possible
- 金属回荡 / Ring / caution_batch_default;tonal_tail_no_auto_promote;tonal_ambience_possible;tonal_tail_or_reverb_possible

## Inputs

- `exports\ai_alias_prompt_pack\ai_alias_candidates_surface_cleaned.csv`

## Canonical token guard

- canonical_tokens_sha256_before: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
- canonical_tokens_sha256_after: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
