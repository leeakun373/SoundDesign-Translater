"""LocalTranslate HTTP 客户端。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TranslateResponse:
    translation: str
    src_lang: str
    tgt_lang: str
    mode: str
    pro_mode: bool
    glossary_hits: int
    direction: str
    ms: int
    debug: dict[str, Any] = field(default_factory=dict)


class LocalTranslateClient:
    def __init__(self, base_url: str = "http://127.0.0.1:18765") -> None:
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def translate(
        self,
        text: str,
        mode: str = "auto",
        pro_mode: bool = True,
    ) -> TranslateResponse:
        payload = {"text": text, "mode": mode, "pro_mode": pro_mode}
        data = self._post("/translate", payload)
        return TranslateResponse(
            translation=data["translation"],
            src_lang=data["src_lang"],
            tgt_lang=data["tgt_lang"],
            mode=data["mode"],
            pro_mode=data["pro_mode"],
            glossary_hits=data["glossary_hits"],
            direction=data["direction"],
            ms=data["ms"],
            debug=data.get("debug", {}),
        )

    def _get(self, path: str) -> dict[str, Any]:
        req = urllib.request.Request(f"{self.base_url}{path}", method="GET")
        return self._read(req)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        return self._read(req)

    def _read(self, req: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(detail)
                message = parsed.get("error", detail)
            except json.JSONDecodeError:
                message = detail
            raise RuntimeError(f"HTTP {exc.code}: {message}") from exc
