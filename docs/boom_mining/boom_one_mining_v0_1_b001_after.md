# BOOM One Mining v0.1 b001 After Report

## Batch

- batch: `boom_one_mining_v0.1_b001`
- source: `boom_mined`
- note: `boom_one_mining_v0.1_b001`
- phase: `auto_promote`
- promoted rows: `21`
- rejected (from promote_ready pool): `13`
- rolled_back: `false`
- AI invoked: `no` (deterministic curated rules; no NLLB / free translation)
- promote: `yes`
- canonical changed: `yes`

## Canonical Guard

- sha256 before: `b05f489338144b42f5cc937a8eec34d6e8a2ed8948191ac75542e8c2ca4da0b9`
- sha256 after: `9b22c33787ef416cd8f059054e96ff247ebf176e7c476a179b06bb8812d5091f`
- changed: `yes`

## Before vs After

| metric | before | after | delta |
| --- | ---: | ---: | ---: |
| pass | 20 | 41 | +21 |
| partial | 0 | 0 | +0 |
| needs_review | 239 | 293 | +54 |
| unknown | 947 | 898 | -49 |
| safety_fail | 0 | 0 | +0 |
| conflict (candidate diagnostic) | 110 | 110 | +0 |

## After Gate

Note: the `conflict` row above is a candidate-diagnostic count (a proposed
alias clashing with an existing canonical, e.g. 飞越 -> Flyby). It is part of
the mining diagnostics and is NOT a gate signal. The gate uses runtime
canonical audit conflicts + promotion-induced conflicts instead.

- gate passed: `true`
- safety_fail_zero: `true`
- runtime_conflict_zero: `true`
- pass_improved: `true`
- unknown_or_needs_review_dropped: `true`

## Safety Fail Details (after)

- none

## Candidate Diagnostic Conflicts (after, not a gate signal)

| row | zh_fxname | en_fxname |
| ---: | --- | --- |
| 3 | Augusta A109 Fly Interior Land 开关关闭序列 01 | Augusta A109 Fly Interior Land Switch Off Sequence 01 |
| 8 | 奥古斯塔 A109 飞越 01 | Augusta A109 Flyby 01 |
| 9 | 奥古斯塔 A109 快速飞越 01 | Augusta A109 Flyby Fast 01 |
| 29 | Augusta A109 着陆开关关闭序列长 01 | Augusta A109 Landing Switch Off Sequence Long 01 |
| 30 | Augusta A109 着陆开关关闭序列长 02 | Augusta A109 Landing Switch Off Sequence Long 02 |
| 31 | Augusta A109 着陆开关关闭序列长 03 | Augusta A109 Landing Switch Off Sequence Long 03 |
| 50 | R22 外部飞越序列 01 | R22 Exterior Flyby Sequence 01 |
| 51 | R22 外部飞越序列 02 | R22 Exterior Flyby Sequence 02 |
| 72 | Uh60 外部飞越序列长 01 | Uh60 Exterior Flyby Sequence Long 01 |
| 73 | Uh60 外部飞越序列长 02 | Uh60 Exterior Flyby Sequence Long 02 |
| 74 | Uh60 外部飞越序列长 03 | Uh60 Exterior Flyby Sequence Long 03 |
| 75 | Uh60 外部飞越序列中号 01 | Uh60 Exterior Flyby Sequence Medium 01 |
| 76 | Uh60 外部飞越序列中号 02 | Uh60 Exterior Flyby Sequence Medium 02 |
| 77 | Uh60 外部飞越序列中号 03 | Uh60 Exterior Flyby Sequence Medium 03 |
| 78 | Uh60 外部飞越序列中号 04 | Uh60 Exterior Flyby Sequence Medium 04 |
| 79 | Uh60 外部飞越序列非常长 01 | Uh60 Exterior Flyby Sequence Very Long 01 |
| 84 | 空客 A320 飞越远方 01 | Airbus A320 Flyby Distant Front 01 |
| 92 | 波音 737 飞越远方 01 | Boeing 737 Flyby Distant Front 01 |
| 97 | 波音 747 飞越遥远的 01 | Boeing 747 Flyby Distant 01 |
| 104 | 波音 777 飞越遥远 01 | Boeing 777 Flyby Distant 01 |
| 105 | 波音 777 飞越远方 01 | Boeing 777 Flyby Distant Front 01 |
| 112 | 波音 787 从左到右飞越遥远的 01 | Boeing 787 Flyby Left To Right Distant 01 |
| 113 | 波音 787 从右到左远距离飞越 01 | Boeing 787 Flyby Right To Left Distant 01 |
| 119 | 庞巴迪里尔喷气式飞机从左到右飞越关闭 01 | Bombardier Learjet Flyby Left To Right Close 01 |
| 120 | 庞巴迪里尔喷气式飞机从左到右远距离飞越 01 | Bombardier Learjet Flyby Left To Right Distant 01 |
| 121 | 庞巴迪里尔喷气式飞机从右到左飞越关闭 01 | Bombardier Learjet Flyby Right To Left Close 01 |
| 122 | 庞巴迪里尔喷气式飞机从右到左远距离飞越 01 | Bombardier Learjet Flyby Right To Left Distant 01 |
| 129 | 庞巴迪私人飞越 Close 01 | Bombardier Private Flyby Close 01 |
| 131 | 庞巴迪私人飞越从左到右关闭 01 | Bombardier Private Flyby Left To Right Close 01 |
| 132 | 庞巴迪私人飞越从左到右遥远 01 | Bombardier Private Flyby Left To Right Distant 01 |
| 133 | 庞巴迪私人飞越从右到左关闭 01 | Bombardier Private Flyby Right To Left Close 01 |
| 134 | 庞巴迪私人飞越从右到左遥远 01 | Bombardier Private Flyby Right To Left Distant 01 |
| 144 | 塞斯纳私人飞越从右到左远距离 01 | Cessna Private Flyby Right To Left Distant 01 |
| 151 | 飞越庭院 01 | Flyby Above Courtyard 01 |
| 152 | 飞越土地 01 | Flyby Land 01 |
| 153 | 飞越陆地 02 | Flyby Land 02 |
| 154 | 飞越陆地 Rev 01 | Flyby Land Rev 01 |
| 155 | 飞越陆地音调嚎叫 01 | Flyby Land Tonal Howl 01 |
| 169 | 大型飞越土地 01 | Large Flyby Land 01 |
| 219 | A10 霹雳飞越 远方 01 | A10 Thunderbolt Flyby Distant 01 |
| 240 | B52 同温层堡垒飞越遥远 01 | B52 Stratofortress Flyby Distant 01 |
| 242 | B52 Stratofortress 从左到右远距离飞越 01 | B52 Stratofortress Flyby Left To Right Distant 01 |
| 243 | B52 同温层堡垒从右到左飞越关闭 01 | B52 Stratofortress Flyby Right To Left Close 01 |
| 244 | B52 同温层堡垒从右到左远距离飞越 01 | B52 Stratofortress Flyby Right To Left Distant 01 |
| 286 | 欧洲战斗机台风飞越 Fast Distant 01 | Eurofighter Typhoon Flyby Fast Distant 01 |
| 288 | 欧洲战斗机台风从左到右快速远距离飞越 01 | Eurofighter Typhoon Flyby Left To Right Fast Distant 01 |
| 290 | 欧洲台风战斗机从右到左快速远距离飞越 01 | Eurofighter Typhoon Flyby Right To Left Fast Distant 01 |
| 297 | F22 猛禽飞越快速关闭 01 | F22 Raptor Flyby Fast Close 01 |
| 298 | F22 猛禽飞越 Fast Distant 01 | F22 Raptor Flyby Fast Distant 01 |
| 299 | F22 猛禽从左到右飞越关闭 01 | F22 Raptor Flyby Left To Right Close 01 |

## Forbidden Broad Check

- passed: `true`

## Single Char Keep Check

- passed: `true`

## Promoted Top 50

| raw | canonical | slot | lang | priority | class | freq |
| --- | --- | --- | --- | ---: | --- | ---: |
| 涡轮 | Turbine | object | zh | 95 | generic | 177 |
| 稳定 | Steady | modifier | zh | 92 | generic | 79 |
| 序列 | Sequence | detail | zh | 92 | generic | 78 |
| 波音 | Boeing | source | zh | 75 | proper_noun | 26 |
| 奥古斯塔 | Augusta | source | zh | 75 | proper_noun | 21 |
| Augusta | Augusta | source | en | 75 | proper_noun | 16 |
| 起飞 | Take Off | action | zh | 90 | generic | 14 |
| 飞行 | Fly | action | zh | 90 | generic | 13 |
| Globemaster | Globemaster | source | en | 75 | proper_noun | 12 |
| Lancer | Lancer | source | en | 75 | proper_noun | 9 |
| Stratofortress | Stratofortress | source | en | 75 | proper_noun | 9 |
| 开关关闭 | Switch Off | action | zh | 90 | generic | 4 |
| 开关关闭序列 | Switch Off Sequence | action | zh | 90 | generic | 4 |
| 涡轮增压 | Turbine Rev Up | action | zh | 90 | generic | 4 |
| 近距 | Close | detail | zh | 92 | generic | 4 |
| 飞走 | Fly Away | action | zh | 90 | generic | 4 |
| Flanker | Flanker | source | en | 75 | proper_noun | 3 |
| Maverick | Maverick | source | en | 75 | proper_noun | 2 |
| 着陆 | Land | action | zh | 90 | generic | 2 |
| 吱吱声 | Creak | action | zh | 90 | generic | 1 |
| 猪群 | Pigs Herd | object | zh | 95 | generic | 1 |

## Rejected Top 50 (with reason)

| raw | canonical | lang | reason | freq |
| --- | --- | --- | --- | ---: |
| Direct | Direct | en | not_in_curated_vocab_or_high_risk | 2 |
| Once | Once | en | not_in_curated_vocab_or_high_risk | 2 |
| RPG | Rpg | en | not_in_curated_vocab_or_high_risk | 2 |
| RPM | Rpm | en | not_in_curated_vocab_or_high_risk | 2 |
| Rides | Rides | en | not_in_curated_vocab_or_high_risk | 2 |
| Scrapyard | Scrapyard | en | not_in_curated_vocab_or_high_risk | 2 |
| Twice | Twice | en | not_in_curated_vocab_or_high_risk | 2 |
| Atmo | Atmo | en | not_in_curated_vocab_or_high_risk | 1 |
| Bing | Bing | en | not_in_curated_vocab_or_high_risk | 1 |
| Chink | Chink | en | not_in_curated_vocab_or_high_risk | 1 |
| Distance | Distance | en | not_in_curated_vocab_or_high_risk | 1 |
| Infested | Infested | en | not_in_curated_vocab_or_high_risk | 1 |
| Sidewinder | Sidewinder | en | not_in_curated_vocab_or_high_risk | 1 |

## Top 20 Fix Samples (needs_review/unknown -> pass)

| row | zh_fxname | before | after | en_fxname |
| ---: | --- | --- | --- | --- |
| 2 | 奥古斯塔 A109 飞走 01 |  | Augusta Fly Away | Augusta A109 Fly Away 01 |
| 3 | Augusta A109 Fly Interior Land 开关关闭序列 01 | Fly Interior Land | Augusta Fly Interior Land Switch Off Sequence | Augusta A109 Fly Interior Land Switch Off Sequence 01 |
| 4 | 奥古斯塔 A109 飞行内部稳定序列 01 |  | Augusta Fly Interior Steady Sequence | Augusta A109 Fly Interior Steady Sequence 01 |
| 5 | 奥古斯塔 A109 飞行内部稳定序列 02 |  | Augusta Fly Interior Steady Sequence | Augusta A109 Fly Interior Steady Sequence 02 |
| 6 | 奥古斯塔 A109 飞行内部稳定序列 03 |  | Augusta Fly Interior Steady Sequence | Augusta A109 Fly Interior Steady Sequence 03 |
| 7 | 奥古斯塔 A109 飞行内部稳定序列 04 |  | Augusta Fly Interior Steady Sequence | Augusta A109 Fly Interior Steady Sequence 04 |
| 23 | 奥古斯塔 A109 Foley Slate 01 | Foley Slate | Augusta Foley Slate | Augusta A109 Foley Slate 01 |
| 27 | Augusta A109 内部发动机怠速 01 | Interior Engine Idle | Augusta Interior Engine Idle | Augusta A109 Interior Engine Idle 01 |
| 59 | R22 外部启动发动机序列 01 |  | Exterior Start Engine Sequence | R22 Exterior Start Engine Sequence 01 |
| 94 | 波音 737 涡轮怠速关闭 01 | Turbine Idle Close | Boeing Turbine Idle Close | Boeing 737 Turbine Idle Close 01 |
| 96 | 波音 747 Flyby Close Front 01 | Flyby Close Front | Boeing Flyby Close Front | Boeing 747 Flyby Close Front 01 |
| 100 | 波音 747 涡轮增压 01 |  | Boeing Turbine Rev Up | Boeing 747 Turbine Rev Up 01 |
| 107 | 波音 777 涡轮怠速关闭 01 | Turbine Idle Close | Boeing Turbine Idle Close | Boeing 777 Turbine Idle Close 01 |
| 109 | 波音 777 涡轮增压 01 |  | Boeing Turbine Rev Up | Boeing 777 Turbine Rev Up 01 |
| 115 | 波音 787 涡轮怠速关闭 01 | Turbine Idle Close | Boeing Turbine Idle Close | Boeing 787 Turbine Idle Close 01 |
| 231 | B1B Lancer Flyby 快速关闭 01 | Flyby Fast Close | Lancer Flyby Fast Close | B1B Lancer Flyby Fast Close 01 |
| 236 | B1B Lancer 涡轮怠速关闭 01 | Turbine Idle Close | Lancer Turbine Idle Close | B1B Lancer Turbine Idle Close 01 |
| 247 | B52 Stratofortress 涡轮怠速关闭 01 | Turbine Idle Close | Stratofortress Turbine Idle Close | B52 Stratofortress Turbine Idle Close 01 |
| 249 | B52 Stratofortress 涡轮增压 01 |  | Stratofortress Turbine Rev Up | B52 Stratofortress Turbine Rev Up 01 |
| 274 | C17 Globemaster Flyby 快速关闭 01 | Flyby Fast Close | Globemaster Flyby Fast Close | C17 Globemaster Flyby Fast Close 01 |

## Top 20 Remaining Unknown (after)

| unknown | count |
| --- | ---: |
| 遥控无人机 | 50 |
| C | 13 |
| 侧卫 | 10 |
| 涡轮全功率直接 | 9 |
| 飞机拟音驾驶舱翻转开关 | 9 |
| 涡轮稳定远距离 | 7 |
| 单飞远 | 7 |
| 中队飞越慢 | 7 |
| 空袭 | 6 |
| 塑料瓶开口 | 6 |
| 空中客车 | 5 |
| 涡轮怠速直接 | 5 |
| 短裤 | 5 |
| 遥控 | 5 |
| 起飞陆地序列 | 5 |
| 炸弹蝇秋季 | 5 |
| 响 | 5 |
| 宇宙 | 5 |
| 外部飞越序列中号 | 4 |
| 涡轮空转直接 | 4 |
