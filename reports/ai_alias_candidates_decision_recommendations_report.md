# AI Alias Candidate Decision Recommendations Report

Recommendation table only. No canonical overwrite, runtime activation, keep, or promotion.

- total_count: `48`
- accept_candidate: `6`
- needs_review: `42`
- reject_candidate: `0`
- conflict_group_count: `1`
- conflict_candidate_count: `2`
- keep appears: `no`
- all_source_ai_candidate: `true`
- all_priority_zero: `true`
- canonical_tokens.csv changed: `no`
- promote: `no`
- CSV: `E:\WorkSpace\SoundDesign Translater\exports\ai_alias_prompt_pack\ai_alias_candidates_decision_recommendations.csv`

## Decisions by canonical

- Chain: accept_candidate=2, needs_review=2, reject_candidate=0
- Crack: accept_candidate=0, needs_review=4, reject_candidate=0
- Door: accept_candidate=0, needs_review=4, reject_candidate=0
- Drop: accept_candidate=0, needs_review=4, reject_candidate=0
- Friction: accept_candidate=4, needs_review=0, reject_candidate=0
- Gun: accept_candidate=0, needs_review=4, reject_candidate=0
- Hit: accept_candidate=0, needs_review=4, reject_candidate=0
- Impact: accept_candidate=0, needs_review=4, reject_candidate=0
- Ring: accept_candidate=0, needs_review=4, reject_candidate=0
- Shot: accept_candidate=0, needs_review=4, reject_candidate=0
- Single Shot: accept_candidate=0, needs_review=4, reject_candidate=0
- Squeak: accept_candidate=0, needs_review=4, reject_candidate=0

## Decisions by review batch

- batch_safe: accept_candidate=6, needs_review=14, reject_candidate=0
- batch_caution: accept_candidate=0, needs_review=16, reject_candidate=0
- batch_weapon: accept_candidate=0, needs_review=12, reject_candidate=0

## Needs review

- 重击声 / Hit / caution_batch_default;ambiguous_with_impact_knock_punch
- 击打声 / Hit / caution_batch_default;ambiguous_with_impact_knock_punch
- 碰击声 / Hit / caution_batch_default;ambiguous_with_impact_knock_punch;raw_multi_canonical_conflict / raw_conflict_001
- 拳击声 / Hit / caution_batch_default;ambiguous_with_impact_knock_punch;fight_specific
- 吱吱声 / Squeak / caution_batch_default;category_pollution_possible
- 尖锐吱响 / Squeak / caution_batch_default;category_pollution_possible
- 挤压吱响 / Squeak / caution_batch_default;category_pollution_possible
- 金属吱响 / Squeak / caution_batch_default;category_pollution_possible
- 脆裂声 / Crack / caution_batch_default;broad_material_spread
- 爆裂脆响 / Crack / caution_batch_default;broad_material_spread
- 劈裂声 / Crack / caution_batch_default;broad_material_spread
- 断裂脆响 / Crack / caution_batch_default;broad_material_spread
- 单发 / Single Shot / weapon_batch_default;phrase_weapon_high_risk
- 单发射击 / Single Shot / weapon_batch_default;phrase_weapon_high_risk
- 单次开火 / Single Shot / weapon_batch_default;phrase_weapon_high_risk
- 单发枪声 / Single Shot / weapon_batch_default;phrase_weapon_high_risk
- 冲击声 / Impact / safe_medium_risk;standard_alias_review
- 重物撞击声 / Impact / safe_medium_risk;standard_alias_review
- 碰击声 / Impact / safe_medium_risk;standard_alias_review;raw_multi_canonical_conflict / raw_conflict_001
- 砸击声 / Impact / safe_medium_risk;standard_alias_review
- 枪械 / Gun / weapon_batch_default;weapon_object_high_risk
- 枪支 / Gun / weapon_batch_default;weapon_object_high_risk
- 火器 / Gun / weapon_batch_default;weapon_object_high_risk
- 枪炮 / Gun / weapon_batch_default;weapon_object_high_risk;broad_weapon_term
- 枪声 / Shot / weapon_batch_default;weapon_action_high_risk
- 炮击声 / Shot / weapon_batch_default;weapon_action_high_risk
- 开火声 / Shot / weapon_batch_default;weapon_action_high_risk
- 发射声 / Shot / weapon_batch_default;weapon_action_high_risk;too_broad_weapon_action
- 链条声 / Chain / safe_low_risk;standard_alias_review;object_slot_sound_event
- 铁链晃动声 / Chain / safe_low_risk;standard_alias_review;object_slot_sound_event
- 开门声 / Door / safe_medium_risk;standard_alias_review;object_slot_sound_event
- 关门声 / Door / safe_medium_risk;standard_alias_review;object_slot_sound_event
- 门板响 / Door / safe_medium_risk;standard_alias_review;object_slot_sound_event
- 门轴吱响 / Door / safe_medium_risk;standard_alias_review;object_slot_sound_event
- 坠落声 / Drop / safe_medium_risk;standard_alias_review
- 落地声 / Drop / safe_medium_risk;standard_alias_review
- 坠地声 / Drop / safe_medium_risk;standard_alias_review
- 跌落声 / Drop / safe_medium_risk;standard_alias_review
- 振铃声 / Ring / caution_batch_default;tonal_ambience_possible
- 余响 / Ring / caution_batch_default;tonal_ambience_possible;tonal_tail_or_reverb_possible
- 回响声 / Ring / caution_batch_default;tonal_ambience_possible;tonal_tail_or_reverb_possible
- 金属回荡 / Ring / caution_batch_default;tonal_ambience_possible;tonal_tail_or_reverb_possible

## Inputs

- `E:\WorkSpace\SoundDesign Translater\exports\ai_alias_prompt_pack\ai_alias_candidates_review_intake.csv`

## Canonical token guard

- canonical_tokens_sha256_before: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
- canonical_tokens_sha256_after: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
