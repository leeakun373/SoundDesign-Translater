# AI Alias Promote Plan Batch 0 v2 Report

This is a dry-run plan only. No runtime row was added.

- input_count: `48`
- planned_count: `4`
- skipped_count: `44`
- surface_input: `true`
- batch_id: `batch0_dry_run_v2`
- canonical_tokens.csv changed: `no`
- promote: `no`
- AI invoked: `no`
- CSV: `exports\ai_alias_prompt_pack\promote_plan_batch0_v2.csv`

## Skip reason counts

- not_accept_candidate: `44`

## Planned rows

- 擦蹭 -> Friction / action / proposed_keep
- 磨蹭 -> Friction / action / proposed_keep
- 铁链 -> Chain / object / proposed_keep
- 锁链 -> Chain / object / proposed_keep

## Plan guardrails

- all plan_action=plan_only: `true`
- all batch_id=batch0_dry_run_v2: `true`
- review_status uses `proposed_keep` only (not runtime keep)
- source uses `ai_candidate_planned_promotion` (not yet in runtime)

## Inputs

- `exports\ai_alias_prompt_pack\ai_alias_candidates_decision_recommendations_v2.csv`

## Canonical token guard

- canonical_tokens_sha256_before: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
- canonical_tokens_sha256_after: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
