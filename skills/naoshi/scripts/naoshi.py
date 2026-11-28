#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""naoshi: kumihan・tsumekomi・ai-kuse の検出をまとめて出す。直す前後で情報が消えていないかも比べる。

使い方:
  uv run --script scripts/naoshi.py check docs/plan.md page.html
  uv run --script scripts/naoshi.py check --only tsumekomi --format findings docs/plan.md
  uv run --script scripts/naoshi.py snapshot docs/plan.md     # 直す前に数値・URL・名前を控える
  uv run --script scripts/naoshi.py compare docs/plan.md      # 直したあとに、控えたものが消えていないか比べる

各スキルは同じリポジトリの skills/ の下（またはインストール先で naoshi と並んだ場所）から読む。
見つからないスキルは飛ばして、その旨を標準エラーに出す。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from types import ModuleType

SKILLS_ROOT = Path(__file__).resolve().parent.parent.parent
ORDER = ["kumihan", "tsumekomi", "ai-kuse"]  # 直す順（全自動 → 構造 → 語）
MD_EXT = {".md", ".markdown"}
HTML_EXT = {".html", ".htm"}


def _load(name: str, path: Path) -> ModuleType | None:
    if not path.is_file():
        return None
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclass が自分のモジュールを引けるように
    spec.loader.exec_module(mod)
    return mod


class Checkers:
    """各スキルの検出スクリプトを import して、共通の指摘の形で返す。"""

    def __init__(self, root: Path = SKILLS_ROOT) -> None:
        self.kumihan = _load("naoshi_kumihan", root / "kumihan" / "scripts" / "kumihan.py")
        self.tsumekomi = _load("naoshi_tsumekomi", root / "tsumekomi" / "scripts" / "tsumekomi.py")
        self.ai_kuse = _load("naoshi_ai_kuse_core", root / "ai-kuse" / "scripts" / "ai_kuse_core.py")
        self._terms = None
        self._limits = None

    def available(self) -> list[str]:
        return [n for n, m in (("kumihan", self.kumihan), ("tsumekomi", self.tsumekomi), ("ai-kuse", self.ai_kuse)) if m]

    def check(self, path: Path, only: list[str] | None = None, text: str | None = None) -> list[dict]:
        text = path.read_text(encoding="utf-8") if text is None else text
        ext = path.suffix.lower()
        use = only or ORDER
        out: list[dict] = []
        if "kumihan" in use and self.kumihan and ext in HTML_EXT:
            out += [f.to_dict() for f in self.kumihan.check(text, str(path))]
        if "tsumekomi" in use and self.tsumekomi and (ext in HTML_EXT or ext in MD_EXT):
            if self._limits is None:
                self._limits, _ = self.tsumekomi.load_limits()
            kind = "html" if ext in HTML_EXT else "md"
            out += self.tsumekomi.scan(text, kind, str(path), None, self._limits)
        if "ai-kuse" in use and self.ai_kuse:
            if self._terms is None:
                self._terms = self.ai_kuse.load_terms()
            allow = self.ai_kuse.load_allow(path.resolve().parent)
            out += [h.to_finding() for h in self.ai_kuse.scan(text, self._terms, str(path), allow)]
        return out


def sort_findings(fs: list[dict]) -> list[dict]:
    order = {s: i for i, s in enumerate(ORDER + ["review"])}
    return sorted(fs, key=lambda f: (f["path"], order.get(f["skill"], 9), f["line"], f.get("col", 0)))


# ---- 情報が消えていないかの比較 ----------------------------------------------------

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,}).*?^\s*\1", re.S | re.M)
URL_RE = re.compile(r"https?://[^\s<>\"'）)\]]+")
CODE_RE = re.compile(r"`([^`\n]+)`")
NUM_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*(?:%|％)?")
NAME_RE = re.compile(r"(?<![\w-])[A-Za-z][A-Za-z0-9_.-]*[A-Za-z0-9](?![\w-])")
TAG_RE = re.compile(r"<[^>]+>")
STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.S | re.I)
STOP_NAMES = {"the", "and", "or", "of", "to", "in", "is", "a", "an", "for", "on", "with"}


def facts(text: str, html: bool) -> dict[str, Counter]:
    """本文から、消えると困る情報（数値・URL・コード・英字の名前）を数える。"""
    if html:
        text = STYLE_RE.sub(" ", text)
        urls = Counter(re.findall(r"""href\s*=\s*["']([^"']+)""", text))
        text = TAG_RE.sub(" ", text)
    else:
        urls = Counter()
    urls.update(URL_RE.findall(text))
    codes = Counter(CODE_RE.findall(text))
    plain = CODE_RE.sub(" ", URL_RE.sub(" ", FENCE_RE.sub(" ", text)))
    nums = Counter(NUM_RE.findall(plain))
    names = Counter(n for n in NAME_RE.findall(plain) if n.lower() not in STOP_NAMES and len(n) >= 3)
    return {"url": urls, "code": codes, "number": nums, "name": names}


def snapshot_path(path: Path) -> Path:
    key = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
    d = Path(tempfile.gettempdir()) / "naoshi"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def missing(before: dict[str, Counter], after: dict[str, Counter]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for kind, cnt in before.items():
        lost = [k for k, n in cnt.items() if after.get(kind, Counter()).get(k, 0) == 0]
        if lost:
            out[kind] = sorted(lost)
    return out


# ---- CLI ---------------------------------------------------------------------

LABEL = {"url": "URL", "code": "コード", "number": "数値", "name": "英字の名前"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="全スキルの検出をまとめて出す")
    c.add_argument("files", nargs="+", type=Path)
    c.add_argument("--only", help="カンマ区切りで使うスキルを絞る（kumihan,tsumekomi,ai-kuse）")
    c.add_argument("--severity", choices=["info", "warn"], default="info")
    c.add_argument("--format", choices=["text", "findings"], default="text")
    s = sub.add_parser("snapshot", help="直す前に数値・URL・名前を控える")
    s.add_argument("files", nargs="+", type=Path)
    m = sub.add_parser("compare", help="控えた数値・URL・名前が消えていないか比べる")
    m.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    for f in args.files:
        if not f.is_file():
            print(f"見つかりません: {f}", file=sys.stderr)
            return 2

    if args.command == "check":
        return cmd_check(args)
    if args.command == "snapshot":
        for f in args.files:
            data = {k: dict(v) for k, v in facts(f.read_text(encoding="utf-8"), f.suffix.lower() in HTML_EXT).items()}
            snapshot_path(f).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            print(f"{f}: 控えた（{', '.join(f'{LABEL[k]} {len(v)}' for k, v in data.items())}）")
        return 0
    # compare
    status = 0
    for f in args.files:
        sp = snapshot_path(f)
        if not sp.is_file():
            print(f"{f}: 控えがない。直す前に snapshot を実行する", file=sys.stderr)
            status = 2
            continue
        before = {k: Counter(v) for k, v in json.loads(sp.read_text(encoding="utf-8")).items()}
        after = facts(f.read_text(encoding="utf-8"), f.suffix.lower() in HTML_EXT)
        lost = missing(before, after)
        if not lost:
            print(f"{f}: 消えた情報なし")
            continue
        status = 1
        print(f"{f}: 直す前にあって、今はないもの（消してよいものか確かめる）")
        for kind, items in lost.items():
            print(f"  {LABEL[kind]}: {' / '.join(items)}")
    return status


def cmd_check(args) -> int:
    only = [s.strip() for s in args.only.split(",")] if args.only else None
    if only:
        bad = [s for s in only if s not in ORDER]
        if bad:
            print(f"知らないスキル: {', '.join(bad)}（{', '.join(ORDER)} のどれか）", file=sys.stderr)
            return 2
    ck = Checkers()
    absent = [s for s in (only or ORDER) if s not in ck.available()]
    for s in absent:
        print(f"{s} が見つからないので飛ばした（{SKILLS_ROOT / s}）", file=sys.stderr)
    rank = {"info": 0, "warn": 1}
    found: list[dict] = []
    for f in args.files:
        found += ck.check(f, only)
    found = sort_findings([x for x in found if rank[x["severity"]] >= rank[args.severity]])

    if args.format == "findings":
        json.dump({"findings": found}, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    if not found:
        print("指摘なし")
        return 0
    by_skill = Counter(x["skill"] for x in found)
    print("指摘 " + str(len(found)) + " 件（" + " / ".join(f"{s} {by_skill[s]}" for s in ORDER if by_skill[s]) + "）\n")
    for x in found:
        loc = f"{x['path']}:{x['line']}" + (f":{x['col']}" if x.get("col") else "")
        print(f"{loc} [{x['severity']}] {x['skill']}/{x['id']}: {x['message']}")
        if x.get("text"):
            print(f"  箇所: {x['text']}")
        if x.get("hint"):
            print(f"  書き換え方の例: {' / '.join(x['hint'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
