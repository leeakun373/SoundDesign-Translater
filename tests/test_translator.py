"""translator 模块离线测试（不触发 NLLB，全部走分词/词典/吸附路径）。"""

from __future__ import annotations

from translator import boom_snap, cedict, fxname_mode, overrides
from translator import segment as seg


def test_segment_keeps_whole_word():
    tokens = [s.text for s in seg.segment("喷火器")]
    assert tokens == ["喷火器"]


def test_segment_protects_ascii_and_numbers():
    tokens = [s.text for s in seg.segment("奥古斯塔 A109 飞走 01")]
    assert "A109" in tokens
    assert "01" in tokens
    assert "奥古斯塔" in tokens


def test_cedict_flamethrower():
    assert cedict.lookup("喷火器") == "flamethrower"


def test_cedict_cleans_classifier_noise():
    assert cedict.lookup("金属") == "metal"


def test_fx_overrides_priority():
    entry = overrides.lookup("短")
    assert entry is not None
    assert entry["canonical"] == "Short"


def test_snap_form_variant():
    result = boom_snap.snap_term("flame thrower", "喷火器")
    assert result.final == "Flamethrower"
    assert result.decision == "snapped_form"


def test_snap_keeps_common():
    result = boom_snap.snap_term("impact", "碰撞")
    assert result.final == "impact"
    assert result.decision == "kept_common"


def test_fxname_flamethrower():
    assert fxname_mode.normalize("喷火器").output_fxname == "Flamethrower"


def test_fxname_proper_noun_exact():
    out = fxname_mode.normalize("奥古斯塔 A109 飞走 01").output_fxname
    assert out == "Augusta A109 Fly Away 01"


def test_fxname_drops_stopwords():
    out = fxname_mode.normalize("远处雷声沉闷的轰鸣").output_fxname
    assert "的" not in out
    assert out.startswith("Distant Thunder")


def test_fxname_wolf_howl_distant_keeps_source():
    result = fxname_mode.normalize("狼嚎远处")
    assert result.output_fxname == "Wolf Howl Distant"
    assert not any(trace.decision == "unknown" for trace in result.traces)


def test_fxname_click_close_door_keeps_door_action():
    result = fxname_mode.normalize("咔哒关上门")
    assert result.output_fxname == "Click Close Door"
    assert not any(trace.decision == "unknown" for trace in result.traces)


def test_fxname_outdoor_insect_chirp():
    result = fxname_mode.normalize("户外虫鸣")
    assert result.output_fxname == "Outdoor Insect Chirp"
    assert not any(trace.decision == "unknown" for trace in result.traces)


def test_fxname_ice_axe_scrape_drops_weak_suffix():
    result = fxname_mode.normalize("冰斧刮擦冰砖的摩擦声")
    assert result.output_fxname == "Ice Axe Scrape Ice Brick Rub"
    assert any(trace.decision == "dropped_suffix" and trace.source_text == "声"
               for trace in result.traces)
    assert not any("Ambience" in (trace.snapped or "") for trace in result.traces)


def test_fxname_engine_idle_rev_no_door():
    result = fxname_mode.normalize("引擎怠速轰油门")
    assert result.output_fxname == "Engine Idle Revving"
    assert "Door" not in result.output_fxname


def test_fxname_deciduous_forest_morning_birds():
    result = fxname_mode.normalize("落叶林清晨鸟叫")
    assert result.output_fxname == "Deciduous Forest Morning Bird Chirp"


def test_fxname_glass_break_not_windshield():
    result = fxname_mode.normalize("玻璃破碎")
    assert result.output_fxname == "Glass Break"


def test_fxname_whoosh_fly_by_drops_yisheng():
    result = fxname_mode.normalize("嗖的一声飞过去")
    assert result.output_fxname == "Whoosh Fly By"
    assert any(trace.decision == "dropped_suffix" and trace.source_text == "一声"
               for trace in result.traces)
