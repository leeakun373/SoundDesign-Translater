# AI Alias Candidate Surface Cleanup Report

Surface cleanup only. No canonical overwrite, runtime activation, keep, or promotion.

- input_count: `48`
- output_count: `48`
- duplicate_dropped_count: `0`
- replaced_raw_count: `15`
- needs_review_count: `15`
- reject_surface_count: `3`
- canonical_tokens.csv changed: `no`
- promote: `no`
- AI invoked: `no`
- CSV: `E:\WorkSpace\SoundDesign Translater\exports\ai_alias_prompt_pack\ai_alias_candidates_surface_cleaned.csv`

## Surface action counts

- keep_raw: `15`
- replace_raw: `15`
- needs_review: `15`
- reject_surface: `3`

## Surface risk counts

- low: `28`
- medium: `12`
- high: `8`

## Replaced raw rows

- 击打声 -> 击打 / Hit / strip_suffix_声
- 碰击声 -> 碰击 / Hit / strip_suffix_声
- 吱吱声 -> 吱吱 / Squeak / strip_suffix_声
- 脆裂声 -> 脆裂 / Crack / strip_suffix_声
- 劈裂声 -> 劈裂 / Crack / strip_suffix_声
- 单发枪声 -> 单发枪 / Single Shot / strip_suffix_声
- 冲击声 -> 冲击 / Impact / strip_suffix_声
- 碰击声 -> 碰击 / Impact / strip_suffix_声
- 砸击声 -> 砸击 / Impact / strip_suffix_声
- 擦蹭声 -> 擦蹭 / Friction / strip_suffix_声
- 磨蹭声 -> 磨蹭 / Friction / strip_suffix_声
- 开火声 -> 开火 / Shot / weapon_fire_action
- 坠落声 -> 坠落 / Drop / strip_suffix_声
- 坠地声 -> 坠地 / Drop / strip_suffix_声
- 跌落声 -> 跌落 / Drop / strip_suffix_声

## Needs review surface rows

- 拳击声 / cleaned=拳击 / Hit / fight_specific_surface
- 重物撞击声 / cleaned=重物撞击 / Impact / surface_too_descriptive
- 表面摩擦音 / cleaned=表面摩擦 / Friction / surface_too_descriptive
- 炮击声 / cleaned=炮击 / Shot / shot_sound_concept
- 发射声 / cleaned=发射 / Shot / too_broad_weapon_action
- 链条声 / cleaned=链条 / Chain / object_slot_sound_event
- 铁链晃动声 / cleaned=铁链晃动 / Chain / object_slot_sound_event
- 开门声 / cleaned=开门 / Door / door_event_not_object
- 关门声 / cleaned=关门 / Door / door_event_not_object
- 门板响 / cleaned=门板响 / Door / object_slot_sound_event
- 门轴吱响 / cleaned=门轴吱响 / Door / hinge_squeak_event
- 振铃声 / cleaned=振铃 / Ring / tonal_ring_surface
- 余响 / cleaned=余响 / Ring / tonal_tail_no_auto_promote
- 回响声 / cleaned=回响声 / Ring / tonal_tail_no_auto_promote
- 金属回荡 / cleaned=金属回荡 / Ring / tonal_tail_no_auto_promote

## Inputs

- `E:\WorkSpace\SoundDesign Translater\exports\ai_alias_prompt_pack\ai_alias_candidates_review_intake.csv`

## Canonical token guard

- canonical_tokens_sha256_before: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
- canonical_tokens_sha256_after: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
