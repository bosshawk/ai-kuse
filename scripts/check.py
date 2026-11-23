#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""AI の文章によく出る語を検出する。

使い方:
  uv run --script scripts/check.py README.md docs/*.md
  cat draft.md | uv run --script scripts/check.py --stdin
  uv run --script scripts/check.py --format json --domain tech draft.md

出力はテキスト（既定）か JSON。言い換えるかどうかは、出力の why / suggest / keep_when を見て文脈で決める。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_kuse_core import load_allow, load_terms, scan  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=Path, help="検査するファイル")
    ap.add_argument("--stdin", action="store_true", help="標準入力から読む")
    ap.add_argument("--domain", action="append", help="使う語の一覧（terms/<domain>.yaml）。複数指定可。既定はすべて")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--severity", choices=["info", "warn"], default="info", help="この重さ以上だけ出す")
    ap.add_argument("--allow", type=Path, help="追加の allow ファイル（1行に id か語）")
    ap.add_argument("--fail-on", choices=["none", "info", "warn"], default="none", help="この重さの指摘があれば終了コード 1")
    args = ap.parse_args(argv)

    if not args.files and not args.stdin:
        ap.error("ファイルを指定するか --stdin を付けてください")

    terms = load_terms(args.domain)
    if not terms:
        print("語の一覧が見つかりません（terms/*.yaml）", file=sys.stderr)
        return 2
    allow = load_allow(Path.cwd(), args.allow)

    hits = []
    if args.stdin:
        hits += scan(sys.stdin.read(), terms, "<stdin>", allow)
    for f in args.files:
        if not f.is_file():
            print(f"見つかりません: {f}", file=sys.stderr)
            return 2
        hits += scan(f.read_text(encoding="utf-8"), terms, str(f), allow)

    rank = {"info": 0, "warn": 1}
    hits = [h for h in hits if rank[h.term.severity] >= rank[args.severity]]

    if args.format == "json":
        json.dump({"count": len(hits), "hits": [h.to_dict() for h in hits]}, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print_text(hits)

    if args.fail_on != "none" and any(rank[h.term.severity] >= rank[args.fail_on] for h in hits):
        return 1
    return 0


def print_text(hits) -> None:
    if not hits:
        print("指摘なし")
        return
    warn = sum(1 for h in hits if h.term.severity == "warn")
    print(f"指摘 {len(hits)} 件（warn {warn} / info {len(hits) - warn}）\n")
    for h in hits:
        t = h.term
        q = " [引用の中]" if h.quoted else ""
        print(f"{h.path}:{h.line}:{h.col} [{t.severity}]{q} {h.matched}（{t.term} / {t.category_label} / {t.id}）")
        print(f"  本文: {h.text.strip()}")
        print(f"  理由: {t.why}")
        print(f"  候補: {' / '.join(t.suggest)}")
        if t.keep_when:
            print(f"  残す場面: {' / '.join(t.keep_when)}")
        print()


if __name__ == "__main__":
    sys.exit(main())
