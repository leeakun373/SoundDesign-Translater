# FXName 中文测试 — 批次 2 计划（50 条）

> 状态：**待编写**  
> 原则：不再平均分 A/B/C/D，按真实失败模式加权。

## 分配

| 类别 | 数量 | 目的 | 代表方向 |
|------|------|------|----------|
| 同词多义消歧 | 15 | 打 / 碰 / 响 / 甩 / 划 同字不同对象 | 打门≠打鼓≠打枪；碰杯≠碰桌；铃响≠金属响 |
| 物体+动作稳定短语 | 10 | 扩充 phrase rule 主表 | 安全、可 `mapped_phrase` + `high` |
| 复合动作 | 10 | 防止只吃第一个动作 | 拉开又关上、倒入溅出、滚动后撞击 |
| 弱 token / 污染词 | 5 | 防止进入 FXName | 响 / 动 / 测试 / 不好听 |
| 真实文件名脏输入 | 10 | Soundminer / 录音素材实际命名 | take 号、mic、声道、主观词剥离 |

## 同词多义消歧（15）— 示例清单

| 中文输入 | expected_fxname | must_not_contain |
|----------|-----------------|------------------|
| 打门 | Door Knock | Hit |
| 打鼓 | Drum Hit | Fire |
| 打枪 | Gun Fire | Hit |
| 打火机 | Lighter Click | Hit |
| 打雷 | Thunder Crack | Hit |
| 打水漂 | Stone Skip Water | Hit |
| 打字 | Keyboard Typing | Hit |
| 打蛋 | Egg Whisk | Hit |
| 打喷嚏 | Sneeze | Hit |
| 打电话 | （review 或 Phone Ring） | Hit |
| 碰杯 | Glass Clink | Impact |
| 车辆碰撞 | Car Crash | Bump |
| 铃响 | Bell Ring | （泛 Ring 无对象） |
| 甩衣服 | Cloth Flap | Whip |
| 划火柴 | Match Strike | Scratch |

## 复合动作（10）— 示例清单

抽屉拉开又关上 · 门打开后撞到墙 · 拿起杯子放下 · 金属盒打开合上 · 拉链拉开再拉上 · 锁扣打开关闭 · 纸张揉皱展开 · 布料甩动落地 · 石头滚动后撞击 · 水倒入杯中溅出

## 脏输入（10）— 示例清单

木门-滑开_01 · 金属门 撞击 A03 · 冰块刮擦冰砖_co100k · 皮革摩擦_MKH8040 · 石头拖地 远景 · 塑料盒掉落 close · 玻璃杯碰杯 双声道 · 门响 不好听 · 乱七八糟的铁片响 · 测试_打_不要用

## 编写规则

1. 每行必须填 `expected_review_status`；有明确输出的填 `expected_fxname`。
2. 消歧类必须填 `must_not_contain`。
3. 脏输入类 `test_kind=result`，重点验 metadata 剥离与 pollution 不进 FXName。
4. 复合动作 `expected_source=composite_phrase`，禁止只输出第一个动词。
