"""A local fake Prune server for mock mode. Free, offline, same wire format as Prune.

It speaks the OpenAI chat/completions format at http://127.0.0.1:8799/v1, so the real Swarms
and LiteLLM code paths run unchanged. It:
  - knows each agent by its mock Prune key (prune_mock_<agent>),
  - answers with mock_content, returns a fake cost and a fake receipt in prune_metadata,
  - checks the Prune headers our code must send (run ID, budget, feature tag),
  - flags likely prompt injection with X-Prune-Shield-Code: prompt_injection_signal (detect mode),
  - can return Prune's real block errors on purpose: set YCC_MOCK_BLOCK="scriptwriter:spend_cap".
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from ycc import mock_content

INJECTION = re.compile(r"ignore (all|previous|your) (instructions|rules)|reveal (the|your) system prompt", re.I)
REQUIRED_HEADERS = ("x-prune-run-id", "x-prune-run-budget-usd", "x-prune-feature-id")
REQUESTS: list[dict] = []  # what the server saw, for tests (never includes keys)


def _cost(prompt_tokens: int, completion_tokens: int) -> float:
    return round(prompt_tokens * 0.15e-6 + completion_tokens * 0.6e-6, 8)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status: int, body: dict, extra_headers: dict | None = None):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Prune-Provider", "mock")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _block(self, code: str, status: int = 429):
        self._send(status, {"error": {"type": "prune_shield", "code": code,
                                      "message": f"Blocked by Prune Shield: {code} (mock)"}},
                   {"X-Prune-Shield-Code": code})

    def do_POST(self):
        if not urlparse(self.path).path.endswith("/chat/completions"):
            return self._send(404, {"error": {"message": "not found"}})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        auth = self.headers.get("Authorization", "")
        key = auth.removeprefix("Bearer ").strip()
        if not key.startswith("prune_mock_"):
            return self._send(401, {"error": {"message": "Mock Prune needs a prune_mock_<agent> key."}})
        agent_id = key.removeprefix("prune_mock_")
        headers = {h: self.headers.get(h) for h in REQUIRED_HEADERS}
        if not all(headers.values()):
            return self._block("run_budget_missing_run_id", 400)

        run_id = headers["x-prune-run-id"]
        week = int(m.group(1)) if (m := re.search(r"week-(\d+)", run_id)) else 1
        phase = headers["x-prune-feature-id"]
        messages = body.get("messages", [])
        user_text = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") != "system")
        REQUESTS.append({"agent": agent_id, "phase": phase, "run_id": run_id, "model": body.get("model"),
                         "has_tools": bool(body.get("tools"))})

        forced = os.environ.get("YCC_MOCK_BLOCK", "")
        if forced and forced.split(":")[0] == agent_id:
            return self._block(forced.split(":")[1])

        shield = {}
        if INJECTION.search(user_text):
            shield = {"X-Prune-Shield-Code": "prompt_injection_signal"}

        wants_orders = bool(body.get("tools"))
        data = mock_content.answer(agent_id, week, user_text, wants_orders, phase)
        content = json.dumps(data)
        p_tok = max(1, len(json.dumps(messages)) // 4)
        c_tok = max(1, len(content) // 4)
        cost = _cost(p_tok, c_tok)
        receipt = "mock-" + hashlib.sha256(f"{run_id}|{agent_id}|{content}".encode()).hexdigest()[:32]

        if wants_orders:
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call_mock_1", "type": "function",
                "function": {"name": body["tools"][0]["function"]["name"], "arguments": content}}]}
            finish = "tool_calls"
        else:
            message = {"role": "assistant", "content": content}
            finish = "stop"

        self._send(200, {
            "id": "mock-" + receipt[5:17], "object": "chat.completion", "created": int(time.time()),
            "model": body.get("model", "mock"),
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": p_tok, "completion_tokens": c_tok, "total_tokens": p_tok + c_tok},
            "prune_metadata": {"cost_usd": cost, "cache_hit": False, "receipt": receipt, "mock": True},
        }, shield)


_server: ThreadingHTTPServer | None = None


def start(host: str = "127.0.0.1", port: int = 8799) -> ThreadingHTTPServer:
    global _server
    if _server is None:
        _server = ThreadingHTTPServer((host, port), Handler)
        threading.Thread(target=_server.serve_forever, daemon=True).start()
    return _server


def stop() -> None:
    global _server
    if _server is not None:
        _server.shutdown()
        _server.server_close()
        _server = None


@contextmanager
def running(base_url: str):
    u = urlparse(base_url)
    start(u.hostname or "127.0.0.1", u.port or 8799)
    try:
        yield
    finally:
        pass  # left running for the rest of the program; stop() is called by tests


if __name__ == "__main__":
    start()
    print("Mock Prune running at http://127.0.0.1:8799/v1 (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop()
