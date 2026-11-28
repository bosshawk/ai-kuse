#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""ワードを追加する前の調査に使う。AI の文章と人の文章で、出現頻度と使い方を比べる。

文章群（corpus）は 3 つ:
  ai      Claude Code の会話ログ（~/.claude/projects）にある Claude の返答と、Claude が Write した .md
  human   Qiita の記事（2019〜2021 年、ストック 20 以上）。ChatGPT 公開前の人の文章
  recent  Qiita の記事（今年、ストック 20 以上）。AI と人の文章が混ざっている

使い方:
  survey.py prepare                    文章群を作る（Qiita は未取得の分だけ取る。1 時間に 60 回まで）
  survey.py count '生の' '素の'         正規表現ごとに 10 万字あたりの件数と比を出す
  survey.py neighbors 層               その字・ワードの直前の言葉ごとに件数と用例を出す
  survey.py samples '裏で(回|待)'       各文章群から用例を抜き出す
  survey.py term sou                   登録済みのワードを検出処理で数え、人の文章で当たった用例を出す
  survey.py evidence [--write]         全ワードの evidence を数え直す（--write で tech.yaml に書く）

データは ${AI_KUSE_DATA:-~/.cache/ai-kuse} に置く。リポジトリには入れない。
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_kuse_core import TERMS_DIR, load_terms, scan, visible_lines  # noqa: E402

DATA = Path(os.environ.get("AI_KUSE_DATA", Path.home() / ".cache" / "ai-kuse"))
CORPUS = DATA / "corpus.json"
NAMES = ("ai", "human", "recent")
JA = re.compile(r"[ぁ-んァ-ヴ一-龥]")
QIITA = "https://qiita.com/api/v2/items"


# ---------- 準備 ----------

def _ai_docs(exclude_sessions: set[str]) -> list[tuple[str, str]]:
    root = Path.home() / ".claude" / "projects"
    seen: set[str] = set()
    docs = []
    for f in root.rglob("*.jsonl"):
        if any(s in str(f) for s in exclude_sessions):
            continue
        session = f.parent.name + "/" + f.stem
        for line in f.open(encoding="utf-8", errors="ignore"):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") != "assistant":
                continue
            for c in d.get("message", {}).get("content", []) or []:
                t = None
                if c.get("type") == "text":
                    t = c.get("text")
                elif c.get("type") == "tool_use" and c.get("name") == "Write" \
                        and str(c.get("input", {}).get("file_path", "")).endswith(".md"):
                    t = c["input"].get("content")
                # ワードそのものを話題にしている文章（このスキルの開発）は外す
                if not t or len(JA.findall(t)) < 30 or "ai-kuse" in t:
                    continue
                h = hashlib.md5(t.encode()).hexdigest()
                if h not in seen:
                    seen.add(h)
                    docs.append((session, t))
    return docs


def _fetch_qiita(prefix: str, query: str, pages: int) -> list[tuple[str, str]]:
    cache = DATA / "qiita"
    cache.mkdir(parents=True, exist_ok=True)
    docs = []
    for page in range(1, pages + 1):
        f = cache / f"{prefix}_{page:02d}.json"
        if not f.exists():
            url = f"{QIITA}?page={page}&per_page=100&query={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "term-survey-script"})
            with urllib.request.urlopen(req, timeout=30) as r:
                f.write_bytes(r.read())
            time.sleep(1)
        items = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(items, dict):  # レート制限などのエラー
            f.unlink()
            raise SystemExit(f"Qiita API のエラー: {items}")
        docs += [(it["id"], it["body"]) for it in items]
    return docs


def prepare(args) -> None:
    year = date.today().year
    raw = {
        "ai": _ai_docs(set(args.exclude_session or [])),
        "human": _fetch_qiita("human", "created:>=2019-01-01 created:<2022-01-01 stocks:>=20", 15),
        "recent": _fetch_qiita(f"recent{year}", f"created:>={year}-01-01 stocks:>=20", 10),
    }
    corpus = {k: [(s, "\n".join(m for _, m, _ in visible_lines(t))) for s, t in v] for k, v in raw.items()}
    size = {k: sum(len(JA.findall(t)) for _, t in v) for k, v in corpus.items()}
    CORPUS.write_text(json.dumps({"made": date.today().isoformat(), "size": size, "docs": corpus}, ensure_ascii=False))
    for k in NAMES:
        print(f"{k:7} {len(corpus[k]):5} 件  日本語 {size[k]:,} 字")
    print(f"保存しました: {CORPUS}")


def _load():
    if not CORPUS.exists():
        raise SystemExit("文章群がありません。先に `survey.py prepare` を実行してください。")
    d = json.loads(CORPUS.read_text(encoding="utf-8"))
    return d["size"], d["docs"], d["made"]


# ---------- 数える ----------

def _per(n: int, size: int) -> float:
    return round(n / size * 1e5, 2)


def count(args) -> None:
    size, docs, _ = _load()
    print(f"{'パターン':24} " + "  ".join(f"{k:>14}" for k in NAMES) + "   ai/human  recent/human")
    for p in args.patterns:
        r = re.compile(p)
        n = {k: sum(len(r.findall(t)) for _, t in docs[k]) for k in NAMES}
        per = {k: _per(n[k], size[k]) for k in NAMES}
        ra = (per["ai"] + 0.01) / (per["human"] + 0.01)
        rr = (per["recent"] + 0.01) / (per["human"] + 0.01)
        cells = "  ".join(f"{per[k]:>7}({n[k]:>5})" for k in NAMES)
        print(f"{p:24} {cells}   {ra:8.1f}  {rr:8.1f}")
    print("\n数値は 10 万字あたりの件数（かっこ内は件数）。")


def neighbors(args) -> None:
    size, docs, _ = _load()
    w = re.escape(args.word)
    r = re.compile(r"([A-Za-z0-9_]+|[ァ-ヴー]+|[一-龥々]+|[ぁ-ん]{1,3}|[^\s]{0,1})\s?" + w + r"([一-龥々]*)")
    for k in ("ai", "human"):
        c: collections.Counter = collections.Counter()
        ex: dict[str, str] = {}
        for _, t in docs[k]:
            for line in t.splitlines():
                for m in r.finditer(line):
                    key = m.group(1) + args.word + m.group(2)
                    c[key] += 1
                    ex.setdefault(key, line[max(0, m.start() - 15):m.end() + 12].strip())
        total = sum(c.values())
        print(f"===== {k}: {total} 件（10 万字 {_per(total, size[k])}）")
        for key, n in c.most_common(args.top):
            print(f"{n:4} {key}  …{ex[key]}")


def _samples(docs, pattern: re.Pattern, n: int, seed: int) -> tuple[int, list[str]]:
    hits = []
    for _, t in docs:
        for line in t.splitlines():
            for m in pattern.finditer(line):
                hits.append(line[max(0, m.start() - 20):m.end() + 15].strip())
    random.Random(seed).shuffle(hits)
    return len(hits), hits[:n]


def samples(args) -> None:
    size, docs, _ = _load()
    r = re.compile(args.pattern)
    for k in NAMES:
        total, hs = _samples(docs[k], r, args.n, args.seed)
        print(f"■ {k}: {total} 件（10 万字 {_per(total, size[k])}）")
        for h in hs:
            print("   …" + h)


def _term_counts(terms, docs):
    out = {t.id: {k: 0 for k in NAMES} for t in terms}
    for k in NAMES:
        for _, text in docs[k]:
            for h in scan(text, terms):
                out[h.term.id][k] += 1
    return out


def term(args) -> None:
    size, docs, _ = _load()
    terms = [t for t in load_terms() if t.id in args.ids]
    if not terms:
        raise SystemExit("その id のワードがありません。")
    counts = _term_counts(terms, docs)
    for t in terms:
        per = {k: _per(counts[t.id][k], size[k]) for k in NAMES}
        print(f"===== {t.id}（{t.term}）  " + "  ".join(f"{k} {per[k]}" for k in NAMES))
        for k in ("human", "ai"):
            hs = []
            for _, text in docs[k]:
                for h in scan(text, [t]):
                    i = h.col - 1
                    hs.append(h.text[max(0, i - 20):i + 15].strip())
            random.Random(args.seed).shuffle(hs)
            label = "人の文章で当たった用例（誤検出でないか読む）" if k == "human" else "AI の文章の用例"
            print(f"  {label}: {len(hs)} 件")
            for x in hs[:args.n]:
                print("    …" + x)


def evidence(args) -> None:
    size, docs, made = _load()
    terms = load_terms()
    counts = _term_counts(terms, docs)
    label = made[:7]
    path = TERMS_DIR / "tech.yaml"
    text = path.read_text(encoding="utf-8")

    def repl(m: re.Match) -> str:
        block, tid = m.group(0), m.group(1)
        if tid not in counts:
            return block
        old = re.search(r"    evidence: \{[^\n]*\}\n", block)
        note = ""
        if old:
            nm = re.search(r", note: '[^']*'", old.group(0))
            note = nm.group(0) if nm else ""
            block = block.replace(old.group(0), "")
        c = counts[tid]
        line = (f"    evidence: {{survey: {label}, ai: {_per(c['ai'], size['ai'])}, "
                f"human2021: {_per(c['human'], size['human'])}, qiita2026: {_per(c['recent'], size['recent'])}{note}}}\n")
        return re.sub(r"(    severity: \w+\n)", r"\1" + line.replace("\\", "\\\\"), block, count=1)

    new = re.sub(r"  - id: ([a-z0-9-]+)\n(?:(?!  - id: ).*\n)*", repl, text)
    for t in terms:
        c = counts[t.id]
        print(f"{t.id:14} ai {_per(c['ai'], size['ai']):6}  human {_per(c['human'], size['human']):6}  recent {_per(c['recent'], size['recent']):6}")
    if args.write:
        path.write_text(new, encoding="utf-8")
        print(f"書きました: {path}")
    else:
        print("（--write を付けると tech.yaml の evidence を書き換えます）")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--exclude-session", action="append", help="外す会話の id（いま調査している会話など）")
    p.set_defaults(func=prepare)
    p = sub.add_parser("count")
    p.add_argument("patterns", nargs="+")
    p.set_defaults(func=count)
    p = sub.add_parser("neighbors")
    p.add_argument("word")
    p.add_argument("--top", type=int, default=60)
    p.set_defaults(func=neighbors)
    p = sub.add_parser("samples")
    p.add_argument("pattern")
    p.add_argument("--n", type=int, default=8)
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(func=samples)
    p = sub.add_parser("term")
    p.add_argument("ids", nargs="+")
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(func=term)
    p = sub.add_parser("evidence")
    p.add_argument("--write", action="store_true")
    p.set_defaults(func=evidence)
    args = ap.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
