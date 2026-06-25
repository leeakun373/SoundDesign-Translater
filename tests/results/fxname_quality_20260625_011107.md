# SD FXName Quality Harness 0.1 报告

- 生成时间：2026-06-25 01:11:07
- 用例数：42（随机 fuzz 追加：0）

## Summary

- total: **42**
- pass: **38** (90.5%)
- needs_review: **4**
- fail: **0**
- bad_phrase_count: **0**
- unknown_count: **3**
- mixed_residue_count: **0**
- empty_count: **0**
- average_output_tokens: **3.1**

## Issue 分布

- **unknown_zh**: 3
- **spacing_suspect**: 1

## Top failures（最差 20 条）

### 1. B00M 风格 木门滑开
- output: `Wood Door Slide Open G B00m Wind`
- quality: **needs_review** | group: problem_sample
- issues: unknown_zh
- matched_bad_phrases: （无）

### 2. 塑料 盒掉 落
- output: `Plastic Box Drop`
- quality: **needs_review** | group: spacing_fuzz
- issues: spacing_suspect
- matched_bad_phrases: （无）

### 3. 门关闭
- output: `Door Close`
- quality: **needs_review** | group: basic_stable
- issues: unknown_zh
- matched_bad_phrases: （无）

### 4. 门打开
- output: `Door Open`
- quality: **needs_review** | group: basic_stable
- issues: unknown_zh
- matched_bad_phrases: （无）

### 5. Glass Break 玻璃
- output: `Glass Break`
- quality: **pass** | group: mixed_english
- issues: （无）
- matched_bad_phrases: （无）

### 6. door 推开 wood
- output: `Wood Door Push Open`
- quality: **pass** | group: mixed_english
- issues: （无）
- matched_bad_phrases: （无）

### 7. exterior 混响 room tone
- output: `Exterior Reverberant Room Tone`
- quality: **pass** | group: mixed_english
- issues: （无）
- matched_bad_phrases: （无）

### 8. metal door 撞击
- output: `Metal Door Impact`
- quality: **pass** | group: mixed_english
- issues: （无）
- matched_bad_phrases: （无）

### 9. plastic box 掉落
- output: `Plastic Box Drop`
- quality: **pass** | group: mixed_english
- issues: （无）
- matched_bad_phrases: （无）

### 10. whoosh 飞过
- output: `Whoosh Flyby`
- quality: **pass** | group: mixed_english
- issues: （无）
- matched_bad_phrases: （无）

### 11. wood door 滑开
- output: `Wood Door Slide Open`
- quality: **pass** | group: mixed_english
- issues: （无）
- matched_bad_phrases: （无）

### 12. 保时 捷外 面轰 油门 驶过
- output: `Exterior Rev Driveby Porsche`
- quality: **pass** | group: problem_sample
- issues: （无）
- matched_bad_phrases: （无）

### 13. 单声 道室 外混 响底 噪
- output: `Exterior Reverberant Room Tone Mono`
- quality: **pass** | group: problem_sample
- issues: （无）
- matched_bad_phrases: （无）

### 14. 塑料盒掉落
- output: `Plastic Box Drop`
- quality: **pass** | group: problem_sample
- issues: （无）
- matched_bad_phrases: （无）

### 15. 布帘拉动
- output: `Cloth Curtain Pull`
- quality: **pass** | group: problem_sample
- issues: （无）
- matched_bad_phrases: （无）

### 16. 引擎 怠速 轰油 门
- output: `Engine Idle Rev`
- quality: **pass** | group: problem_sample
- issues: （无）
- matched_bad_phrases: （无）

### 17. 引擎怠速轰油门
- output: `Engine Idle Rev`
- quality: **pass** | group: spacing_fuzz_base
- issues: （无）
- matched_bad_phrases: （无）

### 18. 打开关闭门
- output: `Open Close Door`
- quality: **pass** | group: problem_sample
- issues: （无）
- matched_bad_phrases: （无）

### 19. 打磨
- output: `Sand`
- quality: **pass** | group: problem_sample
- issues: （无）
- matched_bad_phrases: （无）

### 20. 拖动摩擦停止
- output: `Drag Rub Stop`
- quality: **pass** | group: problem_sample
- issues: （无）
- matched_bad_phrases: （无）

## Bad phrase cases

（无）

## Unknown zh cases

| input | output | quality | issues | matched_bad_phrases |
|---|---|---|---|---|
| 门打开 | `Door Open` | needs_review | unknown_zh | - |
| 门关闭 | `Door Close` | needs_review | unknown_zh | - |
| B00M 风格 木门滑开 | `Wood Door Slide Open G B00m Wind` | needs_review | unknown_zh | - |

## Mixed English / 中文残留 cases

（无）

## Spacing fuzz cases

| input | output | quality | issues | matched_bad_phrases |
|---|---|---|---|---|
| 塑料 盒掉 落 | `Plastic Box Drop` | needs_review | spacing_suspect | - |
| 金属门撞击 | `Metal Door Impact` | pass | - | - |
| 玻璃门滑开 | `Glass Door Slide Open` | pass | - | - |
| 引擎怠速轰油门 | `Engine Idle Rev` | pass | - | - |

## Regression examples

| input | output | quality | issues | matched_bad_phrases |
|---|---|---|---|---|
| B00M 风格 木门滑开 | `Wood Door Slide Open G B00m Wind` | needs_review | unknown_zh | - |
