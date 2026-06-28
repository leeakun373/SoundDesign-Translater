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
