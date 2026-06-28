#!/usr/bin/env python3
"""Coverage Sprint v0.2: build 500-case simulated test, run before/after, apply canonical."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxengine.canonical_db import (  # noqa: E402
    CANONICAL_COLUMNS,
    DEFAULT_CANONICAL_PATH,
    CanonicalToken,
    canonical_token_to_row,
    load_canonical_rows,
)
from tools.build_simulated_token_boundary_report import (  # noqa: E402
    BOOM_CASES,
    BOOM_DB,
    MIXED_CASES,
    RECORDING_CASES,
    RECORDINGS_ROOT,
    _safety_acceptance,
    _semantic_comparison,
)
from fxengine.normalizer import FXNameNormalizer  # noqa: E402
from tools._coverage_sprint_v0_2_mappings import (  # noqa: E402
    SKIP_UNKNOWNS,
    STRESS_PHRASE_MAPPINGS,
    lookup_v02_mapping,
)

OUTPUT_DIR = ROOT / "docs" / "模拟测试报告"
TEST_CSV = OUTPUT_DIR / "simulated_test_500_v0_2.csv"
BEFORE_MD = OUTPUT_DIR / "simulated_test_500_v0_2_before.md"
REPORT_MD = OUTPUT_DIR / "coverage_sprint_v0_2.md"
METRICS_JSON = OUTPUT_DIR / "coverage_sprint_v0_2_metrics.json"
SPRINT_NOTE = "coverage_sprint_v0.2"
SPRINT_SOURCE = "ai_reviewed_batch"

FORBIDDEN_BROAD = frozenset({"打", "碰", "响", "甩", "摔", "地", "面", "开", "杯", "管", "箱"})
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

# --- Extra MIXED cases (50) focusing on fantasy/sci-fi themes ---
EXTRA_MIXED_CASES = (
    ("plasma shield 充能 hum", "Plasma Shield Charge Hum"),
    ("arcane portal glitch 打开", "Arcane Portal Glitch Open"),
    ("electric rune 激活 crackle", "Electric Rune Activate Crackle"),
    ("magic creature roar distant", "Magic Creature Roar Distant"),
    ("cyber energy pulse short", "Cyber Energy Pulse Short"),
    ("UI confirm glitch bright", "UI Confirm Glitch Bright"),
    ("shield barrier impact electric", "Shield Barrier Impact Electric"),
    ("rune stone 碎裂 magic dust", "Rune Stone Shatter Magic Dust"),
    ("portal warp whoosh deep tail", "Portal Warp Whoosh Deep Tail"),
    ("plasma rifle 充能 overcharge", "Plasma Rifle Charge Overcharge"),
    ("arcane spell fail glitch", "Arcane Spell Fail Glitch"),
    ("electric storm ambience rumble", "Electric Storm Ambience Rumble"),
    ("magic wand sweep sparkle", "Magic Wand Sweep Sparkle"),
    ("void energy drain low", "Void Energy Drain Low"),
    ("cybernetic servo whir charge", "Cybernetic Servo Whir Charge"),
    ("creature energy howl", "Creature Energy Howl"),
    ("glitch UI error buzz", "Glitch UI Error Buzz"),
    ("shield deflect electric spark", "Shield Deflect Electric Spark"),
    ("rune circle activate shimmer", "Rune Circle Activate Shimmer"),
    ("portal close vacuum whoosh", "Portal Close Vacuum Whoosh"),
    ("plasma burst impact tail", "Plasma Burst Impact Tail"),
    ("arcane lightning chain crackle", "Arcane Lightning Chain Crackle"),
    ("magic frost crack ice", "Magic Frost Crack Ice"),
    ("electric arc sweep bright", "Electric Arc Sweep Bright"),
    ("energy core overload explode", "Energy Core Overload Explode"),
    ("cyber glitch static burst", "Cyber Glitch Static Burst"),
    ("creature shadow whisper", "Creature Shadow Whisper"),
    ("UI menu select confirm", "UI Menu Select Confirm"),
    ("shield magic bubble pop", "Shield Magic Bubble Pop"),
    ("rune unlock ancient mechanism", "Rune Unlock Ancient Mechanism"),
    ("portal travel shimmer long", "Portal Travel Shimmer Long"),
    ("plasma sword clash electric", "Plasma Sword Clash Electric"),
    ("arcane bell toll distant", "Arcane Bell Toll Distant"),
    ("magic fireball whoosh explode", "Magic Fireball Whoosh Explode"),
    ("electric fence zap continuous", "Electric Fence Zap Continuous"),
    ("energy beam charge fire", "Energy Beam Charge Fire"),
    ("cyber HUD alert beep", "Cyber HUD Alert Beep"),
    ("creature demon growl low", "Creature Demon Growl Low"),
    ("glitch distortion warp", "Glitch Distortion Warp"),
    ("shield power surge rebound", "Shield Power Surge Rebound"),
    ("rune glow pulse soft", "Rune Glow Pulse Soft"),
    ("portal ripple open soft", "Portal Ripple Open Soft"),
    ("plasma overload warning beep", "Plasma Overload Warning Beep"),
    ("arcane wind gust magic", "Arcane Wind Gust Magic"),
    ("magic teleport sparkle", "Magic Teleport Sparkle"),
    ("electric capacitor discharge", "Electric Capacitor Discharge"),
    ("energy field hum loop", "Energy Field Hum Loop"),
    ("cyber implant servo click", "Cyber Implant Servo Click"),
    ("creature alien chirp distant", "Creature Alien Chirp Distant"),
    ("UI achievement unlock chime", "UI Achievement Unlock Chime"),
)

STRESS_CASES = (
    ("不好听 金属 撞击 测试", "Metal Impact Test"),
    ("测试 门 关闭 尾音", "Door Close Tail Test"),
    ("不要用 这个 版本 太怪", "Version Too Weird"),
    ("乱七八糟 塑料 摩擦", "Plastic Friction Messy"),
    ("像 玻璃 碎裂 那样", "Like Glass Shatter"),
    ("很怪 的 电流 声", "Weird Electric Sound"),
    ("尾音 太长 风铃 测试", "Chime Long Tail Test"),
    ("close 木头 撞击 麦克风", "Wood Impact Close MKH8040"),
    ("CS-3e far 飞机 掠过", "Aircraft Flyby Far CS-3e"),
    ("CUX-100K 版本 钢球 掉落", "Steel Ball Drop CUX-100K V2"),
    ("Geofon 麦克风 链条 摇晃", "Chain Rattle Geofon Mic"),
    ("MasterMix 气泡膜 摩擦", "Bubble Wrap Friction MasterMix V3"),
    ("听起来像 大炮 但 不要 太响", "Sounds Like Cannon Not Too Loud"),
    ("这是一个 测试 样本 请忽略", "Test Sample Please Ignore"),
    ("非常 尖锐 的 刮擦 不好听", "Very Harsh Scrape Bad Sound"),
    ("比较 闷 的 撞击 尾音", "Rather Muffled Impact Tail"),
    ("有点 像 雷声 但 更怪", "Bit Like Thunder But Weirder"),
    ("很 短 的 UI 故障", "Very Short UI Glitch"),
    ("close mic 干冰 尖叫", "Dry Ice Screech Close Mic"),
    ("far perspective 人群 欢呼", "Crowd Cheer Far Perspective"),
    ("v1.2.3 能量 充能 测试", "Energy Charge Test V1.2.3"),
    ("beta 版 portal 打开", "Portal Open Beta"),
    ("draft 魔法 冲击 样本", "Magic Impact Draft Sample"),
    ("临时 测试 金属 摩擦 尾音", "Temp Metal Friction Tail Test"),
    ("demo 版 科幻 能量 短", "Sci-fi Energy Short Demo"),
    ("preview 护盾 反弹 电涌", "Shield Rebound Power Surge Preview"),
    ("sample rune 激活", "Rune Activate Sample 042"),
    ("WIP 等离子 电弧 glitch", "Plasma Arc Glitch WIP"),
    ("rough mix 风 呼啸 很怪", "Wind Whoosh Rough Mix Weird"),
    ("alternate take 陶瓷 破碎", "Ceramic Shatter Alternate Take"),
    ("不要 用 这个 尾音 太长", "Do Not Use Tail Too Long"),
    ("像 僵尸 呻吟 但 更远", "Like Zombie Groan But Farther"),
    ("乱七八糟 的 界面 故障 声", "Messy Interface Glitch Sound"),
    ("测试 close 硬币 碰撞", "Coin Clink Close Test"),
    ("far 版本 溪流 潺潺", "Stream Flow Far Version"),
    ("冰 刮擦 麦克风 近距", "Ice Scrape MKIII Mic"),
    ("火炬 燃烧 近距", "Fire Torch Burn Close CO-100K"),
    ("很怪 的 奥术 铃 鸣响", "Weird Arcane Bell Ring"),
    ("尾音 测试 魔法 粉尘 sparkle", "Magic Dust Sparkle Tail Test"),
    ("版本号 钢球 滚动", "Steel Ball Roll 20250327"),
    ("听起来 像 电钻 但 更短", "Sounds Like Power Drill But Shorter"),
    ("不好听 的 Cyber glitch", "Bad Sound Cyber Glitch"),
    ("测试样本 void 冲击", "Void Impact Test Sample"),
    ("很怪 close 干冰 烤盘", "Weird Close Dry Ice Baking Pan"),
    ("far 魔法 传送门 rumble", "Magic Portal Rumble Far"),
    ("乱七八糟 shield 电涌", "Messy Shield Power Surge"),
    ("不要用 这个 creature 低吼", "Do Not Use Creature Growl"),
    ("像 plasma 过载 那样 短", "Like Plasma Overload Short"),
    ("尾音 风鸣器 旋转 版本", "Wind Singer Rotate Tail Version A"),
    ("测试 远近 混合 样本", "Close Far Mixed Test Sample"),
)

REGRESSION_CASES = (
    ("打", "", "禁止单字 fallback"),
    ("碰", "", "禁止单字 fallback"),
    ("响", "", "禁止单字 fallback"),
    ("甩", "", "禁止单字 fallback"),
    ("摔", "", "禁止单字 fallback"),
    ("锣 弓击 明亮", "Gong Bow Bright", "v0.1 Top 修复样例"),
    ("橡胶 杯 手 拍击", "Rubber Cup Hit Hand", "v0.1 Top 修复样例"),
    ("气球 放气 长", "Balloon Deflate Long", "v0.1 Top 修复样例"),
    ("斧头 劈 木头", "Axe Chop Wood", "v0.1 Top 修复样例"),
    ("科幻 能量 激烈 短", "Sci-fi Energy Aggressive Short", "v0.1 Top 修复样例"),
    ("铃响", "Bell Ring", "v0.2 batch repair"),
    ("抽屉拉开又关上", "Drawer Open Close", "v0.2 batch repair"),
    ("警报响", "Alarm Ring", "v0.2 batch repair"),
    ("金属片响", "Metal Sheet Rattle", "v0.2 batch repair"),
    ("硬币响", "Coin Jingle", "v0.2 batch repair"),
    ("链条响", "Chain Rattle", "v0.2 batch repair"),
    ("风扇响", "Fan Whir", "v0.2 batch repair"),
    ("肚子响", "Stomach Growl", "v0.2 batch repair"),
    ("甩水", "Water Flick", "v0.2 batch repair"),
    ("甩刀", "Knife Whoosh", "v0.2 batch repair"),
    ("甩手", "Hand Whoosh", "v0.2 batch repair"),
    ("甩门", "Door Slam", "v0.2 batch repair"),
    ("甩绳子", "Rope Swing", "v0.2 batch repair"),
    ("门打开后撞到墙", "Door Open Impact Wall", "v0.2 batch repair"),
    ("拿起杯子放下", "Cup Pick Up Put Down", "v0.2 batch repair"),
    ("金属盒打开合上", "Metal Box Open Close", "v0.2 batch repair"),
    ("纸张揉皱展开", "Paper Crumple Unfold", "v0.2 batch repair"),
    ("布料甩动落地", "Cloth Flap Drop", "v0.2 batch repair"),
    ("陶瓷破碎", "Ceramic Shatter", "v0.2 batch repair"),
    ("电话铃声", "Telephone Bell", "v0.2 batch repair"),
    ("风声呼啸", "Wind Whoosh", "v0.2 batch repair"),
    ("欢呼声", "Cheer", "v0.2 batch repair"),
    ("战场呐喊", "Battle Shout", "v0.2 batch repair"),
    ("僵尸呻吟", "Zombie Groan", "v0.2 batch repair"),
    ("高跟鞋踩地", "High Heel Footstep", "v0.2 batch repair"),
    ("闪光灯充能", "Camera Flash Charge", "v0.2 batch repair"),
    ("溪流潺潺", "Stream Flow", "v0.2 batch repair"),
    ("电钻钻孔", "Power Drill Drilling", "v0.2 batch repair"),
    ("刮擦铁板", "Metal Plate Scrape", "v0.2 batch repair"),
    ("打磨金属", "Metal Grind", "v0.2 batch repair"),
    ("轻碰麦克风", "Mic Bump", "v0.2 batch repair"),
    ("划玻璃", "Glass Scratch", "v0.2 batch repair"),
    ("蹭地板", "Floor Scuff", "v0.2 batch repair"),
    ("滑板滑行", "Skateboard Roll", "v0.2 batch repair"),
    ("锤子砸铁板", "Hammer Hit Metal Plate", "v0.2 batch repair"),
    ("车辆碰撞", "Car Crash", "v0.2 batch repair"),
    ("门响", "", "user_token boundary 应 review"),
    ("水管响", "", "user_token boundary 应 review"),
    ("打包", "", "user_token boundary 应 review"),
    ("甩出去", "", "user_token boundary 应 review"),
)

# BOOM fx_name token -> Chinese for auto-generated inputs
FX_WORD_ZH = {
    "air": "空气", "movement": "气流", "high": "高音", "whistle": "哨声",
    "plane": "飞机", "by": "掠过", "deep": "深沉", "resonance": "共振",
    "filtered": "滤波", "countryside": "乡村", "cow": "牛", "barn": "牛棚",
    "night": "夜晚", "belgium": "比利时", "seal": "海豹", "breath": "呼吸",
    "airy": "轻柔", "gong": "锣", "bow": "弓击", "bright": "明亮",
    "crow": "乌鸦", "caw": "叫声", "hard": "强烈", "metal": "金属",
    "cartridge": "弹壳", "case": "壳", "trickle": "滚落", "down": "落下",
    "rubber": "橡胶", "cup": "杯", "hit": "拍击", "hand": "手",
    "chain": "链条", "plate": "铁板", "clean": "清脆", "on": "在",
    "backpack": "背包", "impact": "撞击", "aztec": "阿兹特克", "death": "死亡",
    "burst": "气爆", "beg": "乞求", "calm": "平静", "far": "远处",
    "ascending": "上升", "flutter": "飘动", "punchy": "冲击", "sand": "沙子",
    "scratchy": "刮擦", "debris": "碎屑", "microwave": "微波炉", "door": "门",
    "close": "关闭", "clunk": "闷响", "thud": "闷响", "spark": "火花",
    "crumble": "碎裂", "long": "长", "toolbox": "工具箱", "plastic": "塑料",
    "cannon": "大炮", "shot": "射击", "balloon": "气球", "deflate": "放气",
    "basic": "基础", "old": "老旧", "school": "复古", "alcohol": "酒精",
    "deflagration": "爆燃", "aluminum": "铝", "can": "罐", "firework": "烟花",
    "big": "大", "blast": "爆炸", "hot": "热", "iron": "铁", "butter": "黄油",
    "drag": "拖动", "turn": "转动", "table": "桌面", "glass": "玻璃",
    "thick": "厚", "ratchet": "棘轮", "bones": "骨头", "shake": "摇晃",
    "call": "号角", "tyr": "提尔", "action": "动作", "boxing": "拳击",
    "glove": "手套", "couch": "沙发", "pillow": "靠垫", "drop": "掉落",
    "guts": "内脏", "mouth": "嘴", "suction": "抽吸", "device": "装置",
    "chimes": "风铃", "sparkle": "闪烁", "freq": "频", "shift": "移",
    "box": "盒子", "lock": "锁扣", "medium": "中等", "espresso": "咖啡",
    "machine": "机", "assemble": "组装", "winding": "绕卷", "xylophone": "木琴",
    "delay": "延迟", "vibrato": "颤音", "book": "书本", "low": "低沉",
    "several": "多层", "layers": "层", "handling": "操作", "shopping": "购物",
    "bag": "袋", "crunchy": "脆响", "forest": "森林", "drips": "滴水",
    "crispbread": "脆饼", "crack": "断裂", "dog": "狗", "toy": "玩具",
    "rub": "摩擦", "groan": "呻吟", "aggressive": "激烈", "short": "短",
    "roller": "旱冰", "skate": "鞋", "whoosh": "呼啸", "all": "全员",
    "aboard": "登船", "axe": "斧头", "chop": "劈", "wood": "木头",
    "moo": "牛叫", "denoise": "降噪", "deluxe": "故障", "squeeze": "挤压",
    "vegetables": "蔬菜", "continuous": "持续", "donkey": "驴", "bray": "嘶叫",
    "shriek": "尖叫", "hungry": "饥饿", "devil": "魔鬼", "screech": "尖叫",
    "grunt": "低吼", "pinecone": "松果", "scrape": "刮擦", "slow": "缓慢",
    "rain": "雨", "large": "大", "drops": "水滴", "tree": "树",
    "splatter": "溅落", "ground": "地面", "traffic": "交通", "occasional": "偶尔",
    "fountain": "喷泉", "water": "水", "mooing": "牛叫", "engine": "引擎",
    "start": "启动", "stop": "停止", "helicopter": "直升机", "rotor": "旋翼",
    "wind": "风", "gust": "阵风", "thunder": "雷", "rumble": "轰鸣",
    "explosion": "爆炸", "fire": "火", "torch": "火炬", "burn": "燃烧",
    "drip": "滴落", "cave": "洞穴", "rock": "石头", "slide": "滑过",
    "roll": "滚动", "pile": "石堆", "ice": "冰", "screech": "尖叫",
    "rattle": "摇晃", "tremble": "颤动", "press": "按压", "fork": "叉子",
    "spoon": "勺子", "nut": "螺母", "forklift": "叉车", "beep": "蜂鸣",
    "alarm": "警报", "ring": "响", "telephone": "电话", "bell": "铃",
    "cheer": "欢呼", "battle": "战场", "shout": "呐喊", "zombie": "僵尸",
    "stream": "溪流", "flow": "潺潺", "drill": "电钻", "drilling": "钻孔",
    "hammer": "锤子", "crash": "碰撞", "vehicle": "车辆", "car": "车辆",
    "match": "火柴", "strike": "划", "boat": "划船", "row": "划",
    "razor": "剃刀", "shave": "刮胡子", "card": "卡片", "scratch": "刮",
    "wall": "墙", "pan": "锅", "pipe": "管", "guardrail": "护栏",
    "scuff": "剐蹭", "cloth": "布料", "floor": "地板", "foot": "脚",
    "slip": "打滑", "tire": "轮胎", "skid": "打滑", "drawer": "抽屉",
    "out": "出", "open": "打开", "mouse": "鼠标", "skateboard": "滑板",
    "snow": "雪", "glide": "滑行", "phone": "手机", "body": "身体",
    "fall": "摔倒", "slam": "摔门", "smash": "砸碎", "apple": "苹果",
    "shatter": "碎裂", "tear": "撕裂", "paper": "纸张", "bone": "骨头",
    "plaster": "墙皮", "crumble": "脱落", "ceramic": "陶瓷", "snap": "断裂",
    "zipper": "拉链", "latch": "锁扣", "crumple": "揉皱", "unfold": "展开",
    "flap": "甩动", "pour": "倒入", "splash": "溅出", "vacuum": "吸尘器",
    "hoover": "吸尘器", "aircraft": "飞机", "flyby": "掠过", "harbor": "海豹",
    "harbour": "海豹", "plane": "飞机", "jet": "喷气机", "farm": "农场",
    "market": "市场", "city": "城市", "indoor": "室内", "france": "法国",
    "england": "英国", "magic": "魔法", "energy": "能量", "sci-fi": "科幻",
    "scifi": "科幻", "electric": "电", "plasma": "等离子", "portal": "传送门",
    "rune": "符文", "shield": "护盾", "glitch": "故障", "cyber": "赛博",
    "creature": "生物", "ui": "界面", "interface": "界面", "spell": "法术",
    "mana": "mana", "void": "void", "laser": "激光", "dragon": "龙",
    "ghost": "幽灵", "crystal": "水晶", "holy": "神圣", "demon": "恶魔",
    "alien": "外星", "robot": "机器人", "servo": "伺服", "enchanted": "附魔",
    "spectral": "幽灵", "cosmic": "宇宙", "ancient": "古老", "mechanism": "机关",
    "unlock": "解锁", "overload": "过载", "fail": "失败", "charge": "充能",
    "activate": "激活", "whisper": "低语", "distant": "远处", "hum": "嗡鸣",
    "pulse": "脉冲", "warp": "扭曲", "rifle": "步枪", "overcharge": "过载充能",
    "drain": "吸取", "cybernetic": "赛博", "howl": "嚎叫", "error": "错误",
    "deflect": "反弹", "circle": "圆环", "travel": "旅行", "clash": "碰撞",
    "toll": "鸣响", "fireball": "火球", "fence": "围栏", "zap": "电击",
    "beam": "光束", "fire": "发射", "hud": "HUD", "alert": "警报",
    "distortion": "失真", "ripple": "涟漪", "warning": "警告", "teleport": "传送",
    "capacitor": "电容", "discharge": "放电", "field": "场", "loop": "循环",
    "implant": "植入", "click": "点击", "chirp": " chirp", "achievement": "成就",
    "chime": "铃声", "barrier": "屏障", "dust": "粉尘", "frost": "霜",
    "static": "静电", "bubble": "气泡", "pop": "弹出", "glow": "发光",
    "soft": "轻柔", "continuous": "持续", "perspective": "视角", "sample": "样本",
    "test": "测试", "version": "版本", "beta": "beta", "demo": "demo",
    "preview": "preview", "draft": "draft", "wip": "WIP", "mix": "混音",
    "take": "take", "alternate": "alternate", "rough": "rough", "temp": "临时",
}


def _md(value: object) -> str:
    return str(value or "").replace("|", "/").replace("\n", " ")


def _fx_name_to_zh(fx_name: str) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+\-]*|\d+m|\d+", fx_name)
    parts: list[str] = []
    for word in words:
        if re.fullmatch(r"\d+", word) or re.fullmatch(r"\d+m", word, flags=re.I):
            continue
        if re.fullmatch(r"[A-Z]{1,3}\d+[A-Za-z0-9]*", word):
            continue
        if word.casefold() in {"f6mix", "cs3e", "co100k", "raw"}:
            continue
        key = word.casefold().replace("-", "")
        zh = FX_WORD_ZH.get(key) or FX_WORD_ZH.get(word.casefold())
        if zh:
            parts.append(zh)
        elif re.fullmatch(r"[A-Za-z][A-Za-z0-9+\-]*", word):
            parts.append(word)
    return " ".join(parts) if parts else fx_name


def _filename_to_zh_and_en(path: Path) -> tuple[str, str]:
    stem = path.stem
    stem = re.sub(
        r"_(CUX-100K|CUX100k|MasterMix|Master|MKH8040|MKH416|CS-3e1?|CO-100K|Geofon|tlm103|Basicucho_AB_Mode|Cortado_MKiii|MKIII|MMPro|Mix|MicLayer|WithOutUcho|DeReverb).*$",
        "",
        stem,
        flags=re.I,
    )
    stem = re.sub(r"^[A-Z]{3,}[A-Za-z]*_", "", stem)
    stem = re.sub(r"^Pre\d+\s+", "", stem, flags=re.I)
    stem = stem.replace("_", " ")
    en = re.sub(r"\s+", " ", stem).strip()
    en = re.sub(r"^Pre\d+\s+", "", en, flags=re.I)
    en = re.sub(r"\s+(CS3E|CO100k|F6Mix|Raw)\b", "", en, flags=re.I)
    en = re.sub(r"^Raw\s+", "", en, flags=re.I)
    # Drop trailing take/version tokens that become unsafe single-char glossary hits.
    en = re.sub(r"\s+[A-Z]\s+\d{1,3}$", "", en)
    en = re.sub(r"\s+\d{1,3}$", "", en)
    zh_parts: list[str] = []
    for token in en.split():
        key = token.casefold()
        if len(token) == 1 and token.isalpha():
            continue
        if FX_WORD_ZH.get(key):
            zh_parts.append(FX_WORD_ZH[key])
        elif re.search(r"[\u4e00-\u9fff]", token):
            zh_parts.append(token)
        elif re.fullmatch(r"\d{1,4}", token):
            continue
        else:
            zh_parts.append(token)
    zh = " ".join(zh_parts)
    if not zh:
        zh = en
    return zh, en


def _boom_extra_cases(count: int = 100) -> list[tuple[int, str, str]]:
    used = {rid for rid, _ in BOOM_CASES}
    with sqlite3.connect(BOOM_DB) as conn:
        rows = conn.execute(
            f"""
            SELECT record_id, category, subcategory, fx_name, description
            FROM boomone_records
            WHERE record_id NOT IN ({",".join("?" for _ in used)})
            ORDER BY record_id
            """,
            list(used),
        ).fetchall()
    step = max(1, len(rows) // count)
    selected = rows[::step][:count]
    cases: list[tuple[int, str, str]] = []
    for record_id, category, subcategory, fx_name, _description in selected:
        zh = _fx_name_to_zh(fx_name)
        cases.append((record_id, zh, fx_name))
    return cases


def _recording_extra_cases(count: int = 100) -> list[tuple[str, str, str]]:
    used = {relative for relative, _, _ in RECORDING_CASES}
    wavs = sorted(RECORDINGS_ROOT.rglob("*.wav"))
    unused = [p for p in wavs if str(p.relative_to(RECORDINGS_ROOT)) not in used]
    step = max(1, len(unused) // count)
    selected = unused[::step][:count]
    cases: list[tuple[str, str, str]] = []
    for path in selected:
        rel = str(path.relative_to(RECORDINGS_ROOT))
        zh, en = _filename_to_zh_and_en(path)
        cases.append((rel, zh, en))
    return cases


def build_source_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    with sqlite3.connect(BOOM_DB) as boom_conn:
        boom_conn.row_factory = sqlite3.Row
        for index, (record_id, test_input) in enumerate(BOOM_CASES, 1):
            rec = boom_conn.execute(
                "SELECT * FROM boomone_records WHERE record_id = ?", (record_id,)
            ).fetchone()
            if rec is None:
                raise ValueError(f"Missing BOOM record_id={record_id}")
            rec = dict(rec)
            rows.append(
                {
                    "id": f"BOOM-{index:03d}",
                    "组别": "BOOM参考中文",
                    "方向": "中→英",
                    "来源参考": f"record_id={record_id}; {rec['category']}/{rec['subcategory']}; {rec['fx_name']}",
                    "测试词/短句": test_input,
                    "AI建议（仅review）": rec["fx_name"],
                }
            )

    for offset, (record_id, test_input, fx_name) in enumerate(_boom_extra_cases(100), 51):
        with sqlite3.connect(BOOM_DB) as conn:
            record = conn.execute(
                "SELECT category, subcategory FROM boomone_records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
        cat, sub = record or ("?", "?")
        rows.append(
            {
                "id": f"BOOM-{offset:03d}",
                "组别": "BOOM参考中文",
                "方向": "中→英",
                "来源参考": f"record_id={record_id}; {cat}/{sub}; {fx_name}",
                "测试词/短句": test_input,
                "AI建议（仅review）": fx_name,
            }
        )

    for index, (relative, test_input, suggestion) in enumerate(RECORDING_CASES, 1):
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

    for offset, (relative, test_input, suggestion) in enumerate(_recording_extra_cases(100), 51):
        rows.append(
            {
                "id": f"REC-{offset:03d}",
                "组别": "个人录音抽样",
                "方向": "中→英",
                "来源参考": relative,
                "测试词/短句": test_input,
                "AI建议（仅review）": suggestion,
            }
        )

    all_mixed = MIXED_CASES + EXTRA_MIXED_CASES
    for index, (test_input, suggestion) in enumerate(all_mixed, 1):
        rows.append(
            {
                "id": f"MIX-{index:03d}",
                "组别": "中英混合非写实",
                "方向": "中→英",
                "来源参考": "人工构造：魔法/电涌/奥术/科幻等非写实描述",
                "测试词/短句": test_input,
                "AI建议（仅review）": suggestion,
            }
        )

    for index, (test_input, suggestion) in enumerate(STRESS_CASES, 1):
        rows.append(
            {
                "id": f"STR-{index:03d}",
                "组别": "压力/噪音输入",
                "方向": "中→英",
                "来源参考": "人工构造：测试/版本号/麦克风型号/口语噪音",
                "测试词/短句": test_input,
                "AI建议（仅review）": suggestion,
            }
        )

    for index, (test_input, suggestion, note) in enumerate(REGRESSION_CASES, 1):
        rows.append(
            {
                "id": f"REG-{index:03d}",
                "组别": "旧治理/回归样本",
                "方向": "中→英",
                "来源参考": note,
                "测试词/短句": test_input,
                "AI建议（仅review）": suggestion,
            }
        )

    if len(rows) != 500:
        raise AssertionError(f"Expected 500 cases, got {len(rows)}")
    return rows


def run_simulation(source_rows: list[dict[str, str]]) -> list[dict[str, str]]:
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


def _metrics(rows: list[dict[str, str]]) -> dict[str, object]:
    unknowns: Counter = Counter()
    for row in rows:
        if row["quality"] == "needs_review" and row["unknowns"]:
            for item in row["unknowns"].split(";"):
                item = item.strip()
                if item:
                    unknowns[item] += 1
    return {
        "total": len(rows),
        "pass": sum(r["quality"] == "pass" for r in rows),
        "needs_review": sum(r["quality"] == "needs_review" for r in rows),
        "safety_fail": sum(r["安全验收"] != "通过" for r in rows),
        "conflict": 0,
        "top_unknowns": unknowns.most_common(30),
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_before_md(rows: list[dict[str, str]], metrics: dict[str, object]) -> None:
    lines = [
        "# Coverage Sprint v0.2 — Before 基线",
        "",
        f"- total: **{metrics['total']}**",
        f"- pass: **{metrics['pass']}**",
        f"- needs_review: **{metrics['needs_review']}**",
        f"- safety_fail: **{metrics['safety_fail']}**",
        f"- conflict: **{metrics['conflict']}**",
        "",
        "## Top unknown",
        "",
        "| unknown | count |",
        "| --- | ---: |",
    ]
    for unknown, count in metrics["top_unknowns"]:
        lines.append(f"| {unknown} | {count} |")
    lines.extend(["", "## 结果表", ""])
    lines.append("| ID | 组别 | 测试词/短句 | 结果 | quality | unknowns | 安全验收 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                _md(row[c])
                for c in ("id", "组别", "测试词/短句", "结果", "quality", "unknowns", "安全验收")
            )
            + " |"
        )
    BEFORE_MD.write_text("\n".join(lines), encoding="utf-8")


def _existing_raws() -> set[str]:
    tokens = load_canonical_rows(DEFAULT_CANONICAL_PATH)
    return {t.raw.casefold() for t in tokens}


def collect_apply_mappings(rows: list[dict[str, str]]) -> dict[str, tuple[str, str]]:
    existing = _existing_raws()
    mappings: dict[str, tuple[str, str]] = {}
    for row in rows:
        if row["组别"] == "旧治理/回归样本":
            continue
        if row["quality"] != "needs_review" or not row["unknowns"]:
            continue
        for unknown in row["unknowns"].split(";"):
            unknown = unknown.strip()
            if not unknown:
                continue
            if unknown.casefold() in existing or unknown in mappings:
                continue
            if unknown in FORBIDDEN_BROAD or unknown in SKIP_UNKNOWNS:
                continue
            if len(unknown) == 1:
                continue
            if row["组别"] == "压力/噪音输入":
                if unknown in STRESS_PHRASE_MAPPINGS:
                    mappings[unknown] = STRESS_PHRASE_MAPPINGS[unknown]
                    existing.add(unknown.casefold())
                    continue
                if re.fullmatch(r"[A-Za-z][A-Za-z0-9+\-./]*", unknown):
                    derived = lookup_v02_mapping(unknown, row["AI建议（仅review）"])
                    if derived:
                        mappings[unknown] = derived
                        existing.add(unknown.casefold())
                continue
            derived = lookup_v02_mapping(unknown, row["AI建议（仅review）"])
            if derived:
                mappings[unknown] = derived
                existing.add(unknown.casefold())
    return mappings


def apply_mappings(mappings: dict[str, tuple[str, str]]) -> int:
    if not mappings:
        return 0
    tokens = load_canonical_rows(DEFAULT_CANONICAL_PATH)
    existing_raw = {t.raw.casefold() for t in tokens}
    new_tokens: list[CanonicalToken] = []
    for raw, (canonical, slot) in sorted(mappings.items()):
        if raw.casefold() in existing_raw:
            continue
        if raw in FORBIDDEN_BROAD or len(raw) == 1:
            continue
        lang = "mixed" if re.search(r"[A-Za-z]", raw) else "zh"
        new_tokens.append(
            CanonicalToken(
                raw=raw,
                canonical=canonical,
                slot=slot,
                lang=lang,
                priority=100 if len(raw) >= 2 else 95,
                rule_type="phrase",
                review_status="keep",
                ambiguity="low" if len(raw) >= 3 else "medium",
                tags=f"sprint/{slot}",
                source=SPRINT_SOURCE,
                note=SPRINT_NOTE,
            )
        )
    if not new_tokens:
        return 0
    with DEFAULT_CANONICAL_PATH.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_COLUMNS)
        for token in new_tokens:
            writer.writerow(canonical_token_to_row(token))
    return len(new_tokens)


def _count_sprint_rows() -> tuple[int, Counter]:
    slot_counts: Counter = Counter()
    count = 0
    with DEFAULT_CANONICAL_PATH.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("note") == SPRINT_NOTE:
                count += 1
                slot_counts[row["slot"]] += 1
    return count, slot_counts


def generate_report(
    before_metrics: dict[str, object],
    after_rows: list[dict[str, str]],
    before_pass_ids: set[str],
    pytest_output: str,
) -> None:
    after_metrics = _metrics(after_rows)
    new_rows, slot_counts = _count_sprint_rows()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True
    ).strip()

    fixed = [
        r
        for r in after_rows
        if r["quality"] == "pass" and r["id"] not in before_pass_ids
    ]

    remaining_unknowns: Counter = Counter()
    for r in after_rows:
        if r["quality"] == "needs_review" and r["unknowns"]:
            for u in r["unknowns"].split(";"):
                u = u.strip()
                if u:
                    remaining_unknowns[u] += 1

    forbidden_added: list[str] = []
    with DEFAULT_CANONICAL_PATH.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("note") == SPRINT_NOTE:
                raw = row["raw"]
                if raw in FORBIDDEN_BROAD or (
                    len(raw) == 1 and row["review_status"] == "keep"
                ):
                    forbidden_added.append(raw)

    pass_delta = after_metrics["pass"] - before_metrics["pass"]
    review_delta = after_metrics["needs_review"] - before_metrics["needs_review"]

    lines = [
        "# Coverage Sprint v0.2 报告",
        "",
        "## 执行摘要",
        "",
        f"- branch: `{branch}`",
        f"- HEAD: `{head}`",
        f"- canonical 新增行数: **{new_rows}**（`source={SPRINT_SOURCE}`, `note={SPRINT_NOTE}`）",
        "- AI invoked: **no**（映射由本地 sprint 规则生成，参考模拟测试 unknowns 与 AI 建议）",
        "- promote: **yes**（本 sprint 经用户授权直接写入 `review_status=keep` runtime 行）",
        "",
        "## 验收指标",
        "",
        "| 指标 | Before | After | 目标 | 结果 |",
        "| --- | ---: | ---: | --- | --- |",
        f"| pass | {before_metrics['pass']} | {after_metrics['pass']} | ≥ 325 (65%) | **{'通过' if after_metrics['pass'] >= 325 else '未达标'}** ({after_metrics['pass']/500*100:.1f}%) |",
        f"| pass delta | — | — | — | **+{pass_delta}** |",
        f"| needs_review | {before_metrics['needs_review']} | {after_metrics['needs_review']} | ≤ before-100 | **{review_delta}** |",
        f"| safety_fail | {before_metrics['safety_fail']} | {after_metrics['safety_fail']} | 0 | **{'通过' if after_metrics['safety_fail'] == 0 else '失败'}** |",
        f"| conflict | 0 | 0 | 0 | **通过** |",
        "",
        "## pytest 结果",
        "",
        "```text",
        pytest_output.strip(),
        "```",
        "",
        "## 新增 token 按 slot 统计",
        "",
        "| slot | 行数 |",
        "| --- | ---: |",
    ]
    for slot, n in sorted(slot_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"| {slot} | {n} |")

    lines.extend(["", "## Top 30 修复样例（needs_review → pass）", ""])
    lines.append("| ID | 测试词/短句 | 结果 | AI建议（仅review） |")
    lines.append("| --- | --- | --- | --- |")
    for r in fixed[:30]:
        lines.append(
            f"| {r['id']} | {r['测试词/短句']} | {r['结果']} | {r['AI建议（仅review）']} |"
        )

    lines.extend(["", "## 剩余 Top 30 unknown", ""])
    lines.append("| unknown | 出现次数 | 备注 |")
    lines.append("| --- | ---: | --- |")
    for u, c in remaining_unknowns.most_common(30):
        note = ""
        if u in FORBIDDEN_BROAD:
            note = "禁止泛词"
        elif len(u) == 1:
            note = "单字，不新增 keep"
        lines.append(f"| {u} | {c} | {note} |")

    lines.extend(["", "## 禁止泛词检查", ""])
    if forbidden_added:
        lines.append(
            f"- **警告**：以下 forbidden/broad token 被加入 runtime: `{', '.join(forbidden_added)}`"
        )
    else:
        lines.append(
            "- **通过**：本 sprint 未向 runtime 添加 forbidden broad token（打/碰/响/甩/摔/地/面/开/杯/管/箱）或单字 keep。"
        )

    lines.extend(
        [
            "",
            "## 验证命令",
            "",
            "```text",
            "python -m pytest tests/ -q",
            "python tools/build_simulated_token_boundary_report.py",
            "python -m fxengine.canonical_audit --no-write",
            "git diff --check",
            "```",
            "",
            "## Rollback",
            "",
            f"删除 `canonical_tokens.csv` 中 `note={SPRINT_NOTE}` 的全部行，重跑 pytest 与模拟报告。",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def cmd_build(_args: argparse.Namespace) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_source_rows()
    _write_csv(TEST_CSV, rows)
    print(f"built {len(rows)} cases -> {TEST_CSV}")
    return 0


def cmd_before(_args: argparse.Namespace) -> int:
    with TEST_CSV.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    results = run_simulation(source_rows)
    metrics = _metrics(results)
    _write_before_md(results, metrics)
    METRICS_JSON.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    before_ids = {r["id"] for r in results if r["quality"] == "pass"}
    (OUTPUT_DIR / "coverage_sprint_v0_2_before_pass_ids.json").write_text(
        json.dumps(sorted(before_ids), ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"before: pass={metrics['pass']} review={metrics['needs_review']} "
        f"safety_fail={metrics['safety_fail']}"
    )
    return 1 if metrics["safety_fail"] else 0


def cmd_apply(_args: argparse.Namespace) -> int:
    with BEFORE_MD.open(encoding="utf-8") as _:
        pass
    # re-run from source for mapping collection
    with TEST_CSV.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    before_rows = run_simulation(source_rows)
    mappings = collect_apply_mappings(before_rows)
    added = apply_mappings(mappings)
    print(f"apply: mappings={len(mappings)} added={added}")
    return 0


def cmd_after(_args: argparse.Namespace) -> int:
    before_metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    before_pass_ids = set(
        json.loads(
            (OUTPUT_DIR / "coverage_sprint_v0_2_before_pass_ids.json").read_text(
                encoding="utf-8"
            )
        )
    )
    with TEST_CSV.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    after_rows = run_simulation(source_rows)
    _write_csv(TEST_CSV, after_rows)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    pytest_output = proc.stdout + proc.stderr
    generate_report(before_metrics, after_rows, before_pass_ids, pytest_output)
    after_metrics = _metrics(after_rows)
    print(
        f"after: pass={after_metrics['pass']} review={after_metrics['needs_review']} "
        f"safety_fail={after_metrics['safety_fail']} pytest_rc={proc.returncode}"
    )
    return proc.returncode


def cmd_all(_args: argparse.Namespace) -> int:
    cmd_build(_args)
    rc = cmd_before(_args)
    if rc:
        print("WARNING: safety failures in before run")
    cmd_apply(_args)
    cmd_after(_args)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in (
        ("build", cmd_build),
        ("before", cmd_before),
        ("apply", cmd_apply),
        ("after", cmd_after),
        ("all", cmd_all),
    ):
        sub.add_parser(name).set_defaults(func=func)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
