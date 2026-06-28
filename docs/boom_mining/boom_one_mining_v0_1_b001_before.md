# BOOM One Mining v0.1 b001 Before Report

## Batch

- batch: `boom_one_mining_v0.1_b001`
- source: `boom_mined`
- note: `boom_one_mining_v0.1_b001`
- phase: `safe_before_only`
- canonical write: `no`
- AI invoked: `no`
- promote: `no`

## Data Range

- zh sheet title: ` BOOM ONE 发布包`
- en sheet title: `BOOM ONE Release Pack`
- zh header_rows_skipped: `1`
- en header_rows_skipped: `1`
- empty_pair_skipped: `0`
- valid pair count: `1000`
- valid Excel row range: `2` - `1001`
- alignment rule: same Excel row number only; no compressed zip.

## Before Metrics

| metric | count |
| --- | ---: |
| pass | 20 |
| partial | 0 |
| needs_review | 239 |
| unknown | 947 |
| safety_fail | 0 |
| conflict | 110 |

## Top 20 Unknown

| unknown | count |
| --- | ---: |
| 遥控无人机 | 50 |
| 波音 | 26 |
| 奥古斯塔 | 21 |
| Augusta | 16 |
| C | 13 |
| Globemaster | 12 |
| 侧卫 | 10 |
| 涡轮全功率直接 | 9 |
| 飞机拟音驾驶舱翻转开关 | 9 |
| Lancer | 9 |
| Stratofortress | 9 |
| 涡轮稳定远距离 | 7 |
| 单飞远 | 7 |
| 中队飞越慢 | 7 |
| 空袭 | 6 |
| 塑料瓶开口 | 6 |
| 内部飞行序列 | 5 |
| 空中客车 | 5 |
| 涡轮怠速直接 | 5 |
| 短裤 | 5 |

## Top 20 Candidate

Only `promote_ready=true` candidates are shown here. Skipped, unsafe, and conflict rows are kept out of this primary list.

| suggested_raw | suggested_canonical | slot | freq | evidence_diversity |
| --- | --- | --- | ---: | ---: |
| 涡轮 | Turbine | object | 177 | 177 |
| 稳定 | Steady | modifier | 79 | 79 |
| 序列 | Sequence | detail | 78 | 78 |
| 波音 | Boeing | object | 26 | 26 |
| 奥古斯塔 | Augusta | object | 21 | 21 |
| Augusta | Augusta | object | 16 | 16 |
| 起飞 | Take Off | unknown | 14 | 14 |
| 飞行 | Fly | action | 13 | 13 |
| Globemaster | Globemaster | unknown | 12 | 12 |
| Lancer | Lancer | unknown | 9 | 9 |
| Stratofortress | Stratofortress | unknown | 9 | 9 |
| 开关关闭 | Switch Off | action | 4 | 4 |
| 开关关闭序列 | Switch Off Sequence | action | 4 | 4 |
| 涡轮增压 | Turbine Rev Up | action | 4 | 4 |
| 近距 | Close | detail | 4 | 4 |
| 飞走 | Fly Away | action | 4 | 4 |
| Flanker | Flanker | unknown | 3 | 3 |
| Direct | Direct | unknown | 2 | 2 |
| Maverick | Maverick | unknown | 2 | 2 |
| Once | Once | unknown | 2 | 2 |

## Top 20 Partial Samples

| row | zh_fxname | output_fxname | en_fxname |
| ---: | --- | --- | --- |

## Top 20 Needs Review Samples

| row | zh_fxname | output_fxname | en_fxname | issues | unknowns |
| ---: | --- | --- | --- | --- | --- |
| 3 | Augusta A109 Fly Interior Land 开关关闭序列 01 | Fly Interior Land | Augusta A109 Fly Interior Land Switch Off Sequence 01 | unknown_ascii:Augusta;technical_token_excluded:A109;unknown_zh:开关关闭序列;technical_token_excluded:01 | Augusta;开关关闭序列 |
| 8 | 奥古斯塔 A109 飞越 01 | Flyover | Augusta A109 Flyby 01 | unknown_zh:奥古斯塔;technical_token_excluded:A109;technical_token_excluded:01 | 奥古斯塔 |
| 9 | 奥古斯塔 A109 快速飞越 01 | Fast Flyover | Augusta A109 Flyby Fast 01 | unknown_zh:奥古斯塔;technical_token_excluded:A109;technical_token_excluded:01 | 奥古斯塔 |
| 10 | 奥古斯塔 A109 Foley 外门关闭 01 | Foley | Augusta A109 Foley Exterior Door Close 01 | unknown_zh:奥古斯塔;technical_token_excluded:A109;unknown_zh:外门关闭;technical_token_excluded:01 | 奥古斯塔;外门关闭 |
| 11 | Augusta A109 Foley 外门关闭困难 01 | Foley | Augusta A109 Foley Exterior Door Close Hard 01 | unknown_ascii:Augusta;technical_token_excluded:A109;unknown_zh:外门关闭困难;technical_token_excluded:01 | Augusta;外门关闭困难 |
| 12 | Augusta A109 Foley 外门关闭软 01 | Foley | Augusta A109 Foley Exterior Door Close Soft 01 | unknown_ascii:Augusta;technical_token_excluded:A109;unknown_zh:外门关闭软;technical_token_excluded:01 | Augusta;外门关闭软 |
| 13 | 奥古斯塔 A109 Foley 外门打开 01 | Foley | Augusta A109 Foley Exterior Door Open 01 | unknown_zh:奥古斯塔;technical_token_excluded:A109;unknown_zh:外门打开;technical_token_excluded:01 | 奥古斯塔;外门打开 |
| 14 | 奥古斯塔 A109 Foley 外门打开 02 | Foley | Augusta A109 Foley Exterior Door Open 02 | unknown_zh:奥古斯塔;technical_token_excluded:A109;unknown_zh:外门打开;technical_token_excluded:02 | 奥古斯塔;外门打开 |
| 15 | Augusta A109 Foley 外门气动关闭 01 | Foley | Augusta A109 Foley Exterior Door Pneumatic Close 01 | unknown_ascii:Augusta;technical_token_excluded:A109;unknown_zh:外门气动关闭;technical_token_excluded:01 | Augusta;外门气动关闭 |
| 16 | Augusta A109 Foley 外门气动关闭 02 | Foley | Augusta A109 Foley Exterior Door Pneumatic Close 02 | unknown_ascii:Augusta;technical_token_excluded:A109;unknown_zh:外门气动关闭;technical_token_excluded:02 | Augusta;外门气动关闭 |
| 17 | Augusta A109 Foley 外门气动开启 01 | Foley | Augusta A109 Foley Exterior Door Pneumatic Open 01 | unknown_ascii:Augusta;technical_token_excluded:A109;unknown_zh:外门气动开启;technical_token_excluded:01 | Augusta;外门气动开启 |
| 18 | Augusta A109 Foley 外门气动开启短 01 | Foley | Augusta A109 Foley Exterior Door Pneumatic Open Short 01 | unknown_ascii:Augusta;technical_token_excluded:A109;unknown_zh:外门气动开启短;technical_token_excluded:01 | Augusta;外门气动开启短 |
| 19 | Augusta A109 Foley 室内门气动关闭 01 | Foley | Augusta A109 Foley Interior Door Pneumatic Close 01 | unknown_ascii:Augusta;technical_token_excluded:A109;unknown_zh:室内门气动关闭;technical_token_excluded:01 | Augusta;室内门气动关闭 |
| 20 | Augusta A109 Foley 室内踏板 01 | Foley | Augusta A109 Foley Interior Pedals 01 | unknown_ascii:Augusta;technical_token_excluded:A109;unknown_zh:室内踏板;technical_token_excluded:01 | Augusta;室内踏板 |
| 21 | Augusta A109 Foley 室内踏板 02 | Foley | Augusta A109 Foley Interior Pedals 02 | unknown_ascii:Augusta;technical_token_excluded:A109;unknown_zh:室内踏板;technical_token_excluded:02 | Augusta;室内踏板 |
| 22 | Augusta A109 Foley 室内踏板 03 | Foley | Augusta A109 Foley Interior Pedals 03 | unknown_ascii:Augusta;technical_token_excluded:A109;unknown_zh:室内踏板;technical_token_excluded:03 | Augusta;室内踏板 |
| 23 | 奥古斯塔 A109 Foley Slate 01 | Foley Slate | Augusta A109 Foley Slate 01 | unknown_zh:奥古斯塔;technical_token_excluded:A109;technical_token_excluded:01 | 奥古斯塔 |
| 24 | Augusta A109 Foley 窗口滑动打开 01 | Foley | Augusta A109 Foley Window Slide Open 01 | unknown_ascii:Augusta;technical_token_excluded:A109;unknown_zh:窗口滑动打开;technical_token_excluded:01 | Augusta;窗口滑动打开 |
| 27 | Augusta A109 内部发动机怠速 01 | Interior Engine Idle | Augusta A109 Interior Engine Idle 01 | unknown_ascii:Augusta;technical_token_excluded:A109;technical_token_excluded:01 | Augusta |
| 32 | 奥古斯塔 A109 关闭 01 | Close | Augusta A109 Shut Down 01 | unknown_zh:奥古斯塔;technical_token_excluded:A109;technical_token_excluded:01 | 奥古斯塔 |

## Safety Fail Details

- none

## Conflict Details

| row | type | raw | canonical | evidence |
| ---: | --- | --- | --- | --- |
| 3 | existing_canonical_conflict | 关闭 | Switch Off | zh_surface_in_input;target_contains:Switch Off |
| 8 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 9 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 29 | existing_canonical_conflict | 关闭 | Switch Off | zh_surface_in_input;target_contains:Switch Off |
| 30 | existing_canonical_conflict | 关闭 | Switch Off | zh_surface_in_input;target_contains:Switch Off |
| 31 | existing_canonical_conflict | 关闭 | Switch Off | zh_surface_in_input;target_contains:Switch Off |
| 50 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 51 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 72 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 73 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 74 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 75 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 76 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 77 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 78 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 79 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 84 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 92 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 97 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 104 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 105 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 112 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 113 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 119 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 120 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 121 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 122 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 129 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 131 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 132 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 133 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 134 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 144 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 151 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 152 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 153 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 154 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 155 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 169 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 219 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 240 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 242 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 243 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 244 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 286 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 288 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 290 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 297 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 298 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |
| 299 | existing_canonical_conflict | 飞越 | Flyby | zh_surface_in_input;target_contains:Flyby |

## Top 20 Skip Reasons

| skip_reason | count |
| --- | ---: |
| target_not_supporting | 495 |
| single_char_zh | 231 |
| already_covered | 185 |
| existing_canonical_conflict | 110 |
| forbidden_broad_token | 6 |

## Forbidden Broad Check

- passed: `true`
- tokens: ``

## Single Char Keep Check

- passed: `true`
- tokens: ``

## Canonical Write Policy

- This is a safe phase. The script does not write `fxengine/data/canonical_tokens.csv`.
- All candidates remain `review_status=review` and `priority=0`.
- `promote_ready=true` only means a later human/script promote phase may consider the row.
