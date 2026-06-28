"""离线混合翻译引擎：NLLB 打底 + CC-CEDICT 兜底 + BOOM 风格吸附。

模块边界见 docs/TRANSLATOR_ARCHITECTURE.md。该包允许 NLLB 输出进入最终结果，
与受治理的 canonical runtime（fxengine）解耦，不会自动改写 canonical_tokens.csv。
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
