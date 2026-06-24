"""本地翻译 HTTP 服务。"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import NllbTranslator, TranslationError

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("LOCAL_TRANSLATE_PORT", "18765"))

_translator: NllbTranslator | None = None
_load_lock = threading.Lock()
_translate_lock = threading.Lock()
_model_ready = False
_load_error: str | None = None


def get_translator() -> NllbTranslator:
    global _translator
    if _translator is None:
        _translator = NllbTranslator()
    return _translator


def ensure_loaded() -> None:
    global _model_ready, _load_error
    with _load_lock:
        if _model_ready:
            return
        try:
            translator = get_translator()
            translator.load()
            _model_ready = True
            _load_error = None
        except Exception as exc:
            _load_error = str(exc)
            raise


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class TranslateHandler(BaseHTTPRequestHandler):
    server_version = "LocalTranslateHTTP/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            translator = get_translator()
            _json_response(
                self,
                200,
                {
                    "status": "ok" if _model_ready else "loading",
                    "model_ready": _model_ready,
                    "glossary_ready": translator.glossary_ready,
                    "load_error": _load_error,
                },
            )
            return
        _json_response(self, 404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/translate":
            _json_response(self, 404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            data = json.loads(raw) if raw else {}
        except (ValueError, json.JSONDecodeError) as exc:
            _json_response(self, 400, {"error": f"invalid json: {exc}"})
            return

        text = (data.get("text") or "").strip()
        if not text:
            _json_response(self, 400, {"error": "text is required"})
            return

        mode = data.get("mode", "auto")
        pro_mode = bool(data.get("pro_mode", True))

        try:
            ensure_loaded()
        except Exception as exc:
            _json_response(self, 503, {"error": f"model not ready: {exc}"})
            return

        translator = get_translator()
        started = time.perf_counter()
        try:
            with _translate_lock:
                result = translator.translate(text, mode=mode, pro_mode=pro_mode)
        except TranslationError as exc:
            _json_response(self, 500, {"error": str(exc)})
            return

        ms = int((time.perf_counter() - started) * 1000)
        _json_response(
            self,
            200,
            {
                "translation": result.text,
                "src_lang": result.src_lang,
                "tgt_lang": result.tgt_lang,
                "mode": result.mode,
                "pro_mode": result.pro_mode,
                "glossary_hits": result.glossary_hits,
                "debug": result.debug,
                "direction": result.direction_label,
                "ms": ms,
            },
        )


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    print("正在加载模型与术语库，请稍候...")
    ensure_loaded()
    translator = get_translator()
    print(f"就绪: model={translator.is_ready}, glossary={translator.glossary_ready}")
    server = ThreadingHTTPServer((host, port), TranslateHandler)
    print(f"LocalTranslate 服务已启动: http://{host}:{port}")
    print("  GET  /health")
    print('  POST /translate  {"text": "...", "mode": "auto", "pro_mode": true}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.server_close()


if __name__ == "__main__":
    run_server()
