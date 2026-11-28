#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Claude Code の PostToolUse hook（Write|Edit|MultiEdit）。

Markdown か HTML が保存されたら:
  1. HTML なら kumihan fix を実行する（lang="ja" と組版CSS。スクリプトだけで直る）
  2. tsumekomi と ai-kuse の warn を上位5件まで、Claude に返す（終了コード 2）

判断が要るもの（info、review）は返さない。指摘をゼロにさせる hook ではない。
環境変数 AI_KUSE_HOOK=0 で止まる。
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAX_REPORT = 5
TARGET_EXT = {".md", ".markdown", ".html", ".htm"}


def load_naoshi():
    path = REPO / "skills" / "naoshi" / "scripts" / "naoshi.py"
    spec = importlib.util.spec_from_file_location("ai_kuse_hook_naoshi", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def run(payload: dict) -> tuple[int, str]:
    if os.environ.get("AI_KUSE_HOOK", "1") == "0":
        return 0, ""
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not file_path:
        return 0, ""
    path = Path(file_path)
    if path.suffix.lower() not in TARGET_EXT or not path.is_file():
        return 0, ""

    naoshi = load_naoshi()
    ck = naoshi.Checkers()
    notes: list[str] = []

    if path.suffix.lower() in (".html", ".htm") and ck.kumihan:
        html = path.read_text(encoding="utf-8")
        new, done = ck.kumihan.fix(html)
        if new != html:
            path.write_text(new, encoding="utf-8", newline="")
            notes.append(f"kumihan が {path.name} を書き換えた（{'、'.join(done)}）。次に編集する前に読み直すこと。")

    found = [f for f in ck.check(path, ["tsumekomi", "ai-kuse"]) if f["severity"] == "warn"]
    found = naoshi.sort_findings(found)
    if found:
        notes.append(
            f"{path.name} に詰め込みや AI の口癖の warn が {len(found)} 件ある。"
            "その場で書き換えるか、残す理由を1行で書くこと（見せ方をそろえる必要はない）。"
        )
        for f in found[:MAX_REPORT]:
            hint = f" 例: {' / '.join(f['hint'][:2])}" if f.get("hint") else ""
            notes.append(f"- {f['path']}:{f['line']} {f['skill']}/{f['id']}: {f['message']}{hint}")
        if len(found) > MAX_REPORT:
            notes.append(f"- ほか {len(found) - MAX_REPORT} 件（naoshi check で全部見られる）")

    if not notes:
        return 0, ""
    return 2, "\n".join(notes)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    try:
        code, message = run(payload)
    except Exception as e:  # hook の失敗で作業を止めない
        print(f"ai-kuse hook でエラー（無視して続けてよい）: {e}", file=sys.stderr)
        return 0
    if message:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
