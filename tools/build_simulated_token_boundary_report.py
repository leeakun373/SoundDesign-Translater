#!/usr/bin/env python3
"""Build a deterministic 150-case report for Chinese user-token boundaries."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxengine.canonical_db import cleanup_chinese_user_token
from fxengine.normalizer import FXNameNormalizer
from fxengine.tokenizer import FXTokenizer


OUTPUT_DIR = ROOT / "docs" / "模拟测试报告"
BOOM_DB = ROOT / "data" / "boomone" / "boomone_records.sqlite"
RECORDINGS_ROOT = Path(r"E:\Audio_Assets\02_Personal_Library\01_Recordings")
CANONICAL_PATH = ROOT / "fxengine" / "data" / "canonical_tokens.csv"
CANONICAL_SHA256_BEFORE = "e769db799302935b49fbe39a176aca7e44de1bef816c2553659f4a5041e3e1af"

BOOM_CASES = (
    (8753, "吸尘器 气流 高音 哨声"),
    (8748, "飞机 掠过 深沉 共振 滤波"),
    (1, "乡村 牛棚 夜晚 比利时"),
    (406, "海豹 呼吸 轻柔"),
    (13838, "锣 弓击 明亮"),
    (720, "乌鸦 叫声 强烈"),
    (13846, "金属 弹壳 滚落"),
    (7032, "橡胶 杯 手 拍击"),
    (8032, "链条 铁板 清脆"),
    (6698, "背包 撞击"),
    (852, "阿兹特克 死亡哨 气爆"),
    (10118, "人群 乞求 平静 远处"),
    (1171, "上升 飘动 冲击"),
    (6703, "沙子 刮擦 碎屑"),
    (17093, "微波炉 门 关闭 闷响"),
    (14019, "火花 碎裂 长尾"),
    (18534, "塑料 工具箱 关闭"),
    (1655, "大炮 射击"),
    (18779, "气球 放气 长"),
    (1696, "基础 打击 复古"),
    (13124, "酒精 爆燃 铝罐"),
    (13213, "烟花 大爆炸"),
    (13197, "热铁 黄油 长"),
    (6743, "卡片 拖动 转动 桌面"),
    (6782, "厚玻璃 棘轮"),
    (6791, "骨头 摇晃"),
    (2132, "大 链条"),
    (16818, "提尔 号角"),
    (1712, "上升 动作 移动"),
    (8327, "拳击手套 沙发 靠垫 重摔"),
    (6792, "内脏 嘴 气泡"),
    (17313, "抽吸 装置"),
    (1733, "上升 风铃 闪烁 频移"),
    (17314, "盒子 关闭 锁扣 中等"),
    (6851, "咖啡机 组装"),
    (17533, "空气感 绕卷"),
    (1736, "木琴 延迟 闪烁 颤音"),
    (6877, "书本 掉落 低沉"),
    (6932, "多层 纸张 近距离 操作"),
    (6957, "购物袋 脆响 用力"),
    (233, "森林 滴水"),
    (6964, "脆饼 断裂"),
    (7837, "狗玩具 摩擦 呻吟 长"),
    (14656, "科幻 能量 激烈 短"),
    (6995, "老式 旱冰鞋 滚动"),
    (2008, "呼啸 全员登船"),
    (18612, "斧头 劈 木头"),
    (18834, "牛叫盒 长"),
    (2093, "界面 故障 降噪"),
    (13589, "挤压 蔬菜 持续"),
)

RECORDING_CASES = (
    (r"01_FoleyDiary\250327_VariousMarbles\CERMImpt_STEEL BALL Fall Tile Sharp Bright Clink_CUX-100K.wav", "钢球 掉落 瓷砖 清脆 明亮 叮当", "Steel Ball Fall Tile Sharp Bright Clink"),
    (r"01_FoleyDiary\250327_VariousMarbles\MECHMisc_MAGNET Interact DUMBBELL Heavy Clank_CUX-100K.wav", "磁铁 碰撞 哑铃 沉重 叮当", "Magnet Dumbbell Heavy Clank"),
    (r"01_FoleyDiary\250327_VariousMarbles\METLMvmt_GEAR Rolling Wood Floor Muffled Rattle_MasterMix.wav", "齿轮 滚动 木地板 闷响 摇晃", "Gear Roll Wood Floor Muffled Rattle"),
    (r"01_FoleyDiary\250412_VariousFruits\Cabbage_Knife_Stab_MasterMix_WithOutUcho.wav", "卷心菜 刀 刺入", "Cabbage Knife Stab"),
    (r"01_FoleyDiary\250412_VariousFruits\Watermelon_Cut_Axe_Basicucho_AB_Mode.wav", "西瓜 斧头 切割", "Watermelon Axe Cut"),
    (r"01_FoleyDiary\250412_VariousFruits\Watermelon_Stab_CUX100k.wav", "西瓜 刺入", "Watermelon Stab"),
    (r"01_FoleyDiary\250412_VariousMetal\Pre412_Sword_Impact_Mid_MasterMix_WithOutUcho.wav", "剑 撞击 中等", "Sword Impact Medium"),
    (r"01_FoleyDiary\250412_VariousMetal\Pre418_Swrod_Trowel_Scrape_Ringout_CS-3e1.wav", "剑 泥刀 刮擦 余响", "Sword Trowel Scrape Ringout"),
    (r"01_FoleyDiary\250412_VariousMetal\Pre423_Sword_Iron_Bar_Friction_Long_MasterMix.wav", "剑 铁杆 摩擦 长", "Sword Iron Bar Friction Long"),
    (r"01_FoleyDiary\250412_VariousMetal\Pre425_Chain_Gear_Metal_Rubbing_Cortado_MKiii.wav", "链条 齿轮 金属 摩擦", "Chain Gear Metal Friction"),
    (r"01_FoleyDiary\250430_TungstenCarbide\SFXMeta_TungstenCarbide_Drop_Concrete_LongPiece_02_CS-3e1.wav", "碳化钨 掉落 混凝土 长条", "Tungsten Carbide Drop Concrete Long Piece"),
    (r"01_FoleyDiary\250430_TungstenCarbide\SFXMeta_TungstenCarbide_Drop_Concrete_SmallPiece_04_Basicucho_AB_Mode.wav", "碳化钨 掉落 混凝土 小块", "Tungsten Carbide Drop Concrete Small Piece"),
    (r"01_FoleyDiary\250430_TungstenCarbide\SFXMeta_TungstenCarbide_Scrape_Concrete_Texture_02_CUX100k.wav", "碳化钨 刮擦 混凝土 纹理", "Tungsten Carbide Scrape Concrete Texture"),
    (r"01_FoleyDiary\250525_SewingMachine_Cymbal_iron_Balloon\CYMBAL_Drag_RubberRod_Small_Dry_Geofon.wav", "镲片 拖动 橡胶棒 小 干", "Cymbal Drag Rubber Rod Small Dry"),
    (r"01_FoleyDiary\250525_SewingMachine_Cymbal_iron_Balloon\SEWING MACHINE_Turn_Handwheel_Left_Old_Medium_Tail_CO-100K.wav", "缝纫机 转动 手轮 左 老旧 中等 尾音", "Sewing Machine Turn Handwheel Left Old Medium Tail"),
    (r"01_FoleyDiary\250525_SewingMachine_Cymbal_iron_Balloon\SEWING MACHINE_Turn_Handwheel_Right_Old_Fast_Tail_Geofon.wav", "缝纫机 转动 手轮 右 老旧 快速 尾音", "Sewing Machine Turn Handwheel Right Old Fast Tail"),
    (r"01_FoleyDiary\250525_SewingMachine_Cymbal_iron_Balloon\SEWING MACHINE_Turn_Handwheel_Right_Old_Slow_Tail_MKH8040_L.wav", "缝纫机 转动 手轮 右 老旧 缓慢 尾音", "Sewing Machine Turn Handwheel Right Old Slow Tail"),
    (r"01_FoleyDiary\250601_MOGANSHAN\MECHClik_ArcadeStick_03_Geofon.wav", "街机摇杆 点击", "Arcade Stick Click"),
    (r"01_FoleyDiary\250606_WindSinger\RUBRTonl_WINDSINGER_Rotate_Latex_Rubber_Backward_whoosh_02_Master.wav", "风鸣器 旋转 乳胶 橡胶 向后 呼啸", "Wind Singer Rotate Latex Rubber Backward Whoosh"),
    (r"01_FoleyDiary\250608_BubbleWrap\PLASMvmt_BubbleWarp_Rub_Crinkle_Crumple_Handle_MKH8040.wav", "气泡膜 摩擦 褶皱 揉皱 操作", "Bubble Wrap Rub Crinkle Crumple Handle"),
    (r"01_FoleyDiary\250611_DryBoxDoor\DOORCreak_DRY BOX DOOR Medium Creak Layer Complex_02_CO-100K.wav", "干燥箱门 中等 吱呀 复杂", "Dry Box Door Medium Creak Complex"),
    (r"01_FoleyDiary\250615_OLYMPUS830\MOTRSrvo_OLYMPUS CAMERA Zoom In Out Rocker Switch Motor_MMPro.wav", "奥林巴斯相机 变焦 进出 摇杆 开关 马达", "Olympus Camera Zoom In Out Rocker Switch Motor"),
    (r"01_FoleyDiary\250619_Material Test 1\CERMMvmt_STEEL BALL Roll Textured Tile Back Steady Scrape_MKH8040.wav", "钢球 滚动 纹理瓷砖 返回 稳定 刮擦", "Steel Ball Roll Textured Tile Back Steady Scrape"),
    (r"01_FoleyDiary\250627_Yunara Foley\CERMImpt_CERAMIC BOWL Stack Impact Brittle_CO-100K.wav", "陶瓷碗 堆叠 撞击 易碎", "Ceramic Bowl Stack Impact Brittle"),
    (r"01_FoleyDiary\250627_Yunara Foley\WOODImpt_BAMBOO CHOPSTICKS Empty Click Collision_MKH416.wav", "竹筷 空心 点击 碰撞", "Bamboo Chopsticks Hollow Click Collision"),
    (r"01_FoleyDiary\250628_HouTanPark\METLImpt_WOOD STICK Hit Steel Wall Poke_MasterMix.wav", "木棍 击打 钢墙 戳", "Wood Stick Hit Steel Wall Poke"),
    (r"01_FoleyDiary\251120_BubbleTeaBear\AIRBlow_Thick Hollow Wood Tube Blow Air.wav", "厚 空心 木管 吹气", "Thick Hollow Wood Tube Blow Air"),
    (r"01_FoleyDiary\251120_BubbleTeaBear\WATRFlow_Water Balloon Drop Ground.wav", "水气球 掉落 地面", "Water Balloon Drop Ground"),
    (r"02_FieldRecording\2507_YinZhouClimbingPark\Raw_FirePart\Raw_Fire Torch Burn Drips - Cave_MKH416.wav", "火炬 燃烧 滴落 洞穴", "Fire Torch Burn Drips Cave"),
    (r"02_FieldRecording\2507_YinZhouClimbingPark\Raw_FirePart_DeReverb\Raw_Fire Gas Can Flame Burst - SHT - Cave Mouth_02_DeReverb_CO-100K.wav", "汽油罐 火焰 爆发 短 洞口", "Gas Can Flame Burst Short Cave Mouth"),
    (r"02_FieldRecording\2507_YinZhouClimbingPark\Raw_RockPart\Raw_Rock Block Slide Rock - CLS - Cave Mouth_02_Geofon.wav", "石块 滑过 岩石 洞口", "Rock Block Slide Rock Close Cave Mouth"),
    (r"02_FieldRecording\2507_YinZhouClimbingPark\Raw_RockPart\Raw_Rock MED Roll on Pile Debris - MED - Cave_MKH8040.wav", "中型石头 滚过 碎屑堆 洞穴", "Medium Rock Roll Debris Pile Cave"),
    (r"02_FieldRecording\2507_YinZhouClimbingPark\Raw_RockPart_DeReverb\Raw_Rock MED Impact Pile - CLS - Cave_01_DeReverb_Mix.wav", "中型石头 撞击 石堆 洞穴", "Medium Rock Impact Pile Close Cave"),
    (r"03_PropSet\250731_DryIce\MicLayer\Dry Ice - Baking Pan - Screech on Wood_01_CS-3e.wav", "干冰 烤盘 木头 尖叫", "Dry Ice Baking Pan Screech Wood"),
    (r"03_PropSet\250731_DryIce\MicLayer\Dry Ice - Bowl - Screech Rattle Tremble_02_MKH8040.wav", "干冰 碗 尖叫 摇晃 颤动", "Dry Ice Bowl Screech Rattle Tremble"),
    (r"03_PropSet\250731_DryIce\MicLayer\Dry Ice - Copper Lid - Press on Wood_CO-100K.wav", "干冰 铜盖 按压 木头", "Dry Ice Copper Lid Press Wood"),
    (r"03_PropSet\250731_DryIce\MicLayer\Dry Ice - Dumbbell - Press Screech_02_CO-100K.wav", "干冰 哑铃 按压 尖叫", "Dry Ice Dumbbell Press Screech"),
    (r"03_PropSet\250731_DryIce\MicLayer\Dry Ice - Fork - Screech Tremble on Wood_01_CO-100K.wav", "干冰 叉子 尖叫 颤动 木头", "Dry Ice Fork Screech Tremble Wood"),
    (r"03_PropSet\250731_DryIce\MicLayer\Dry Ice - Ladder Handrail Mid - Screech Dampened_01_CS-3e.wav", "干冰 楼梯扶手 中等 尖叫 沉闷", "Dry Ice Ladder Handrail Medium Screech Dampened"),
    (r"03_PropSet\250731_DryIce\MicLayer\Dry Ice - Ladder Tread Mid - Screech Dampened_01_MKH8040.wav", "干冰 楼梯踏板 中等 尖叫 沉闷", "Dry Ice Ladder Tread Medium Screech Dampened"),
    (r"03_PropSet\250731_DryIce\MicLayer\Dry Ice - Nut - Screech Rattle Tremble_02_tlm103.wav", "干冰 螺母 尖叫 摇晃 颤动", "Dry Ice Nut Screech Rattle Tremble"),
    (r"03_PropSet\250731_DryIce\MicLayer\Dry Ice - Spoon - Screech Tremble on Wood_02_MKH8040.wav", "干冰 勺子 尖叫 颤动 木头", "Dry Ice Spoon Screech Tremble Wood"),
    (r"03_PropSet\250731_DryIce\MicLayer\Dry Ice - Tuning Fork - Screech Rattle Tremble Press on Wood_tlm103.wav", "干冰 音叉 尖叫 摇晃 颤动 按压 木头", "Dry Ice Tuning Fork Screech Rattle Tremble Press Wood"),
    (r"03_PropSet\250731_DryIce\Mix\Dry Ice - Copper Can - Friction Roll Granular on Wood_01_Mix.wav", "干冰 铜罐 摩擦 滚动 颗粒 木头", "Dry Ice Copper Can Friction Roll Granular Wood"),
    (r"03_PropSet\250731_DryIce\Mix\Dry Ice - Metal Skewer - Rattle Tremble on Wood_Mix.wav", "干冰 金属签 摇晃 颤动 木头", "Dry Ice Metal Skewer Rattle Tremble Wood"),
    (r"03_PropSet\250804_ICE\MicLayer\Raw_ICE - Ice Axe Scratch - Friction Ice Brick 01_MKIII.wav", "冰 斧 刮擦 摩擦 冰砖", "Ice Axe Scratch Friction Ice Brick"),
    (r"03_PropSet\250804_ICE\MicLayer\Raw_ICE - Large Ice Cubes - Mutual Press 01_CO100k.wav", "大冰块 相互 按压", "Large Ice Cubes Mutual Press"),
    (r"03_PropSet\250804_ICE\MicLayer\Raw_ICE - Thin Ice - Nutcracker 01_MKH8040.wav", "薄冰 胡桃夹", "Thin Ice Nutcracker"),
    (r"03_PropSet\250804_ICE\Mix\Raw_ICE - Tin Foil Pan - Round Demold 01_MIX.wav", "冰 锡纸盘 圆形 脱模", "Ice Tin Foil Pan Round Demold"),
    (r"03_PropSet\251129_GlassRing\GLASTonl_Straight Glass Sustained Ring.wav", "直玻璃 持续 鸣响", "Straight Glass Sustained Ring"),
)

MIXED_CASES = (
    ("metal 摩擦 anvil 刺耳的", "Metal Friction Anvil Harsh"),
    ("magic 电涌 impact long tail", "Magic Power Surge Impact Long Tail"),
    ("arcane 能量 burst", "Arcane Energy Burst"),
    ("魔法 whoosh 上升", "Magic Whoosh Rise"),
    ("electric 奥术 crackle", "Electric Arcane Crackle"),
    ("plasma 电弧 short impact", "Plasma Arc Short Impact"),
    ("rune 激活 shimmer", "Rune Activate Shimmer"),
    ("portal 打开 deep whoosh", "Portal Open Deep Whoosh"),
    ("spell 充能 闪烁", "Spell Charge Sparkle"),
    ("mana 爆发 bright tail", "Mana Burst Bright Tail"),
    ("dragon 呼吸 fire burst", "Dragon Breath Fire Burst"),
    ("ghost 低语 distant", "Ghost Whisper Distant"),
    ("crystal 共振 magic", "Crystal Resonance Magic"),
    ("void 冲击 low rumble", "Void Impact Low Rumble"),
    ("thunder 电涌 arcane", "Thunder Power Surge Arcane"),
    ("cyber 魔法 glitch", "Cyber Magic Glitch"),
    ("laser 奥术 sweep", "Laser Arcane Sweep"),
    ("metal door 魔法撞击", "Metal Door Magic Impact"),
    ("energy core 过载", "Energy Core Overload"),
    ("ancient 符文 hum", "Ancient Rune Hum"),
    ("electric chain 摇晃", "Electric Chain Rattle"),
    ("magic 护盾 impact", "Magic Shield Impact"),
    ("plasma 剑 whoosh", "Plasma Sword Whoosh"),
    ("arcane 铃 ring", "Arcane Bell Ring"),
    ("portal 关闭 heavy", "Portal Close Heavy"),
    ("spell 失败 glitch", "Spell Fail Glitch"),
    ("fireball 爆炸 long tail", "Fireball Explosion Long Tail"),
    ("ice 魔法 crack", "Ice Magic Crack"),
    ("shadow 移动 soft", "Shadow Movement Soft"),
    ("holy 风铃 bright", "Holy Chime Bright"),
    ("demon 低吼 distant", "Demon Growl Distant"),
    ("alien 装置 charge", "Alien Device Charge"),
    ("robot servo 电涌", "Robot Servo Power Surge"),
    ("magical 布料 flap", "Magical Cloth Flap"),
    ("enchanted 玻璃 shatter", "Enchanted Glass Shatter"),
    ("rune 石头 impact", "Rune Stone Impact"),
    ("arcane 水 splash", "Arcane Water Splash"),
    ("electric 风暴 ambience", "Electric Storm Ambience"),
    ("magic 粉尘 sparkle", "Magic Dust Sparkle"),
    ("void 传送门 rumble", "Void Portal Rumble"),
    ("sword 奥术碰撞", "Sword Arcane Collision"),
    ("shield 电涌反弹", "Shield Power Surge Rebound"),
    ("wand 魔法挥动", "Wand Magic Whoosh"),
    ("crystal 电流碎裂", "Crystal Electric Shatter"),
    ("spectral 链条 rattle", "Spectral Chain Rattle"),
    ("mana 光束 sweep", "Mana Beam Sweep"),
    ("ancient 机关 unlock", "Ancient Mechanism Unlock"),
    ("cosmic 爆炸 deep tail", "Cosmic Explosion Deep Tail"),
    ("magic 界面 confirm", "Magic Interface Confirm"),
    ("arcane 警报 ring", "Arcane Alarm Ring"),
)

RESULT_COLUMNS = (
    "id",
    "组别",
    "方向",
    "来源参考",
    "测试词/短句",
    "结果",
    "quality",
    "unknowns",
    "语义对照",
    "AI建议（仅review）",
    "安全验收",
    "验收说明",
)


def _boom_rows() -> list[dict[str, str]]:
    if not BOOM_DB.is_file():
        raise FileNotFoundError(BOOM_DB)
    ids = [record_id for record_id, _ in BOOM_CASES]
    placeholders = ",".join("?" for _ in ids)
    with sqlite3.connect(BOOM_DB) as connection:
        connection.row_factory = sqlite3.Row
        records = {
            row["record_id"]: row
            for row in connection.execute(
                f"SELECT * FROM boomone_records WHERE record_id IN ({placeholders})",
                ids,
            )
        }
    rows: list[dict[str, str]] = []
    for index, (record_id, test_input) in enumerate(BOOM_CASES, 1):
        record = records.get(record_id)
        if record is None:
            raise ValueError(f"Missing BOOM record_id={record_id}")
        rows.append(
            {
                "id": f"BOOM-{index:03d}",
                "组别": "BOOM参考中文",
                "方向": "中→英",
                "来源参考": (
                    f"record_id={record_id}; {record['category']}/{record['subcategory']}; "
                    f"{record['fx_name']}"
                ),
                "测试词/短句": test_input,
                "AI建议（仅review）": record["fx_name"],
            }
        )
    return rows


def _recording_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, (relative, test_input, suggestion) in enumerate(RECORDING_CASES, 1):
        source = RECORDINGS_ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        rows.append(
            {
                "id": f"REC-{index:03d}",
                "组别": "个人录音抽样",
                "方向": "中→英",
                "来源参考": relative,
                "测试词/短句": test_input,
                "AI建议（仅review）": suggestion,
            }
        )
    return rows


def _mixed_rows() -> list[dict[str, str]]:
    return [
        {
            "id": f"MIX-{index:03d}",
            "组别": "中英混合非写实",
            "方向": "中→英",
            "来源参考": "人工构造：魔法/电涌/奥术等非写实描述",
            "测试词/短句": test_input,
            "AI建议（仅review）": suggestion,
        }
        for index, (test_input, suggestion) in enumerate(MIXED_CASES, 1)
    ]


def _semantic_comparison(actual: str, suggestion: str) -> str:
    if actual.casefold() == suggestion.casefold():
        return "命中建议"
    if not actual:
        return "无final，待review"
    actual_words = set(actual.casefold().split())
    suggestion_words = set(suggestion.casefold().split())
    if actual_words & suggestion_words:
        return "部分命中"
    return "结果与建议不同，待review"


def _safety_acceptance(test_input: str, result) -> tuple[str, str]:
    reasons: list[str] = []
    raw_tokens = FXTokenizer().tokenize(test_input)
    protected_cores = [
        cleanup_chinese_user_token(token.raw)
        for token in raw_tokens
        if token.kind == "zh_user"
    ]
    protected_cores = [core for core in protected_cores if core]
    result_raws = [token.raw for token in result.tokens]
    missing_cores = [core for core in protected_cores if core not in result_raws]
    if missing_cores:
        reasons.append("user_token未整体保留:" + "/".join(missing_cores))
    unsafe_singles = [
        token.raw
        for token in result.tokens
        if token.source == "glossary_fallback" and len(token.raw) == 1
    ]
    if unsafe_singles:
        reasons.append("单字glossary进入final:" + "/".join(unsafe_singles))
    if "刺耳" in test_input and "Stab" in result.output_fxname.split():
        reasons.append("刺耳错误映射为Stab")
    if result.debug.get("nllb_fallback_used"):
        reasons.append("NLLB进入FXName")
    if reasons:
        return "失败", "; ".join(reasons)
    if result.unknowns:
        return "通过", "未知项保持完整并留在review"
    return "通过", "全部token安全映射"


def build_rows() -> list[dict[str, str]]:
    source_rows = _boom_rows() + _recording_rows() + _mixed_rows()
    if len(source_rows) != 150:
        raise AssertionError(f"Expected 150 cases, got {len(source_rows)}")
    normalizer = FXNameNormalizer()
    results: list[dict[str, str]] = []
    for source in source_rows:
        result = normalizer.normalize(source["测试词/短句"])
        acceptance, reason = _safety_acceptance(source["测试词/短句"], result)
        results.append(
            {
                **source,
                "结果": result.output_fxname,
                "quality": result.quality,
                "unknowns": ";".join(result.unknowns),
                "语义对照": _semantic_comparison(
                    result.output_fxname, source["AI建议（仅review）"]
                ),
                "安全验收": acceptance,
                "验收说明": reason,
            }
        )
    return results


def _write_csv(rows: list[dict[str, str]]) -> Path:
    path = OUTPUT_DIR / "模拟测试结果.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _md(value: object) -> str:
    return str(value or "").replace("|", "/").replace("\n", " ")


def _write_report(rows: list[dict[str, str]]) -> Path:
    path = OUTPUT_DIR / "模拟测试报告.md"
    canonical_after = hashlib.sha256(CANONICAL_PATH.read_bytes()).hexdigest()
    quality_counts = Counter(row["quality"] for row in rows)
    group_counts = Counter(row["组别"] for row in rows)
    semantic_counts = Counter(row["语义对照"] for row in rows)
    safety_counts = Counter(row["安全验收"] for row in rows)
    lines = [
        "# 中文 user_token 边界模拟测试报告",
        "",
        "## 范围与结论",
        "",
        "- 总计：**150** 条；BOOM 本地数据参考 50、个人录音库抽样 50、中英混合非写实描述 50。",
        "- 方向：全部为 **中→英 FXName Normalize**。",
        "- AI invoked：**no**。`AI建议（仅review）` 来自 BOOM FXName、录音文件语义人工整理或人工构造目标，不参与 final output。",
        "- promote：**no**。",
        "- canonical changed：**yes**；仅新增用户明确授权的 `刺耳 → Harsh` 1 行，不属于 Batch Repair 或 AI promote。",
        f"- canonical SHA256 before: `{CANONICAL_SHA256_BEFORE}`",
        f"- canonical SHA256 after: `{canonical_after}`",
        "- 安全验收检查：显式中文 user_token 保持完整、无未治理单字 glossary 进入 final、无 NLLB fallback、`刺耳` 不得输出 `Stab`。",
        "",
        "## 汇总",
        "",
        f"- group counts: `{json.dumps(dict(group_counts), ensure_ascii=False)}`",
        f"- quality counts: `{json.dumps(dict(quality_counts), ensure_ascii=False)}`",
        f"- semantic comparison: `{json.dumps(dict(semantic_counts), ensure_ascii=False)}`",
        f"- safety acceptance: `{json.dumps(dict(safety_counts), ensure_ascii=False)}`",
        "",
        "`needs_review` 不等于 parser 失败：它表示未命中 exact canonical/完整 glossary 的 user_token 被整体保留在 review，没有拆字污染 final。",
        "",
        "## 结果表",
        "",
        "| ID | 组别 | 方向 | 测试词/短句 | 结果 | quality | unknowns | AI建议（仅review） | 语义对照 | 安全验收 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                _md(row[column])
                for column in (
                    "id",
                    "组别",
                    "方向",
                    "测试词/短句",
                    "结果",
                    "quality",
                    "unknowns",
                    "AI建议（仅review）",
                    "语义对照",
                    "安全验收",
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 数据来源",
            "",
            f"- BOOM SQLite: `{BOOM_DB}`",
            f"- Personal recordings: `{RECORDINGS_ROOT}`",
            "- 个人录音采用 1866 个 WAV 按完整路径排序后的等距确定性抽样（50 条），源相对路径保存在 CSV。",
            "",
            "## Rollback",
            "",
            "删除 `canonical_tokens.csv` 中 note 为 `user-authorized token-boundary parser test` 的 `刺耳` 行，撤销 parser/tokenizer、fixture 与审计计数改动，然后重新运行全量 pytest 与本报告生成器。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    csv_path = _write_csv(rows)
    report_path = _write_report(rows)
    failures = [row for row in rows if row["安全验收"] != "通过"]
    print(
        f"simulated token-boundary report: rows={len(rows)} "
        f"pass={sum(row['quality'] == 'pass' for row in rows)} "
        f"needs_review={sum(row['quality'] == 'needs_review' for row in rows)} "
        f"safety_failures={len(failures)}"
    )
    print(f"csv={csv_path}")
    print(f"report={report_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
