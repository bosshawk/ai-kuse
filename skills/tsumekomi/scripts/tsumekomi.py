#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""日本語の文書で、1か所に詰め込みすぎている所を測る（Markdown と HTML）。

使い方:
  uv run --script scripts/tsumekomi.py docs/plan.md page.html
  uv run --script scripts/tsumekomi.py --format findings --severity warn docs/plan.md
  uv run --script scripts/tsumekomi.py --profile reference docs/api.md
  cat draft.md | uv run --script scripts/tsumekomi.py --stdin --type md

測るのは見出し・一文・箇条書きの項目・表のセル・カード・段落の長さ。目安は limits.yaml にある。
仮名を含まない要素（英語やコード）は測らない。コードブロック・インラインコード・URL は数えない。
直すか残すか、どう直すかは測った結果を見て文脈で決める。このスクリプトは形を決めない。

文書ごとの指定（Markdown のコメント。HTML でも同じ）:
  <!-- tsumekomi: profile=reference -->   このファイルの目安を reference にする
  <!-- tsumekomi-ignore -->                この行（Markdown）を測らない
  <!-- tsumekomi-disable --> … <!-- tsumekomi-enable -->  範囲を測らない
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).resolve().parent.parent
LIMITS_PATH = SKILL_DIR / "limits.yaml"

KANA_RE = re.compile(r"[ぁ-ゖァ-ヺ]")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
PROFILE_RE = re.compile(r"tsumekomi:\s*profile\s*=\s*([\w-]+)")
INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
URL_RE = re.compile(r"https?://\S+")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
TAG_RE = re.compile(r"<[^>]+>")
EMPH_RE = re.compile(r"\*\*|__|~~")
SPACE_RE = re.compile(r"\s+")
OPEN_BR = "「『（(“【［["
CLOSE_BR = "」』）)”】］]"
ENDERS = "。！？!?"

IGNORE = "tsumekomi-ignore"
DISABLE = "tsumekomi-disable"
ENABLE = "tsumekomi-enable"
CARD_CLASS_RE = re.compile(r"(^|[\s_-])card([\s_-]|$)", re.I)
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
SKIP_TAGS = {"script", "style", "pre", "code", "template", "svg", "math"}


# ---- 目安 -----------------------------------------------------------------

@dataclass
class Limit:
    id: str
    label: str
    target: str
    measure: str  # chars | sentences
    info: int
    warn: int
    why: str
    hint: list[str]
    keep_when: list[str]
    profiles: dict = field(default_factory=dict)

    def thresholds(self, profile: str) -> tuple[int, int]:
        p = self.profiles.get(profile) or {}
        return p.get("info", self.info), p.get("warn", self.warn)


def load_limits(path: Path = LIMITS_PATH) -> tuple[list[Limit], dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    limits = [
        Limit(
            id=r["id"], label=r["label"], target=r["target"], measure=r["measure"],
            info=r["info"], warn=r["warn"], why=r["why"],
            hint=list(r.get("hint", [])), keep_when=list(r.get("keep_when", []) or []),
            profiles=r.get("profiles", {}) or {},
        )
        for r in data["limits"]
    ]
    return limits, data.get("profiles", {})


# ---- 文字の数え方 ----------------------------------------------------------

def clean_md(s: str) -> str:
    """Markdown の記号・コード・URL を除いた、読み手が読む文字だけにする。"""
    s = INLINE_CODE_RE.sub(lambda m: m.group(0).strip("`"), s)
    s = IMAGE_RE.sub(r"\1", s)
    s = LINK_RE.sub(r"\1", s)
    s = URL_RE.sub("", s)
    s = TAG_RE.sub("", s)
    s = EMPH_RE.sub("", s)
    return s


def count_chars(s: str) -> int:
    return len(SPACE_RE.sub("", s))


def is_japanese(s: str) -> bool:
    return bool(KANA_RE.search(s))


def split_sentences(s: str) -> list[tuple[int, str]]:
    """(開始位置, 文) の一覧。カギ括弧やかっこの中の句点では切らない。"""
    out: list[tuple[int, str]] = []
    depth = 0
    start = 0
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in OPEN_BR:
            depth += 1
        elif c in CLOSE_BR and depth > 0:
            depth -= 1
        elif c in ENDERS and depth == 0:
            j = i + 1
            while j < n and s[j] in ENDERS + CLOSE_BR:
                j += 1
            seg = s[start:j]
            if seg.strip():
                out.append((start, seg))
            start = j
            i = j
            continue
        i += 1
    tail = s[start:]
    if tail.strip():
        out.append((start, tail))
    return out


# ---- 文書を要素に分ける ------------------------------------------------------

@dataclass
class Block:
    kind: str  # heading | list-item | table-cell | paragraph | card
    line: int
    text: str
    line_starts: list[tuple[int, int]] = field(default_factory=list)  # (text 内の位置, 行番号)

    def line_at(self, offset: int) -> int:
        line = self.line
        for pos, no in self.line_starts:
            if pos <= offset:
                line = no
            else:
                break
        return line


class MdCollector:
    def __init__(self) -> None:
        self.blocks: list[Block] = []
        self.cur: Block | None = None
        self.cur_parts: list[tuple[int, str]] = []
        self.profile: str | None = None

    def flush(self) -> None:
        if self.cur is None:
            return
        text = ""
        starts: list[tuple[int, int]] = []
        for no, part in self.cur_parts:
            part = part.strip()
            if not part:
                continue
            if text and text[-1].isascii() and part[0].isascii():
                text += " "
            starts.append((len(text), no))
            text += part
        self.cur.text = text
        self.cur.line_starts = starts
        if text:
            self.blocks.append(self.cur)
        self.cur = None
        self.cur_parts = []

    def start(self, kind: str, no: int, text: str) -> None:
        self.flush()
        self.cur = Block(kind, no, "")
        self.cur_parts = [(no, clean_md(text))]

    def parse(self, text: str) -> list[Block]:
        lines = text.splitlines()
        in_fence = None
        disabled = False
        i0 = 0
        if lines and lines[0].strip() == "---":  # front matter
            for k in range(1, len(lines)):
                if lines[k].strip() in ("---", "..."):
                    i0 = k + 1
                    break
        for idx in range(i0, len(lines)):
            no = idx + 1
            line = lines[idx]
            fm = FENCE_RE.match(line)
            if in_fence:
                if fm and fm.group(1)[0] == in_fence[0] and len(fm.group(1)) >= len(in_fence):
                    in_fence = None
                continue
            if fm:
                self.flush()
                in_fence = fm.group(1)
                continue
            pm = PROFILE_RE.search(line)
            if pm:
                self.profile = pm.group(1)
                continue
            if DISABLE in line:
                self.flush()
                disabled = True
                continue
            if ENABLE in line:
                disabled = False
                continue
            if disabled or IGNORE in line:
                continue
            stripped = line.strip()
            if not stripped:
                self.flush()
                continue
            if stripped.startswith("<!--") and stripped.endswith("-->"):
                continue
            hm = HEADING_RE.match(line)
            if hm:
                self.start("heading", no, hm.group(2))
                self.flush()
                continue
            if stripped.startswith("|"):
                self.flush()
                if TABLE_SEP_RE.match(stripped):
                    continue
                for cell in split_cells(stripped):
                    c = clean_md(cell)
                    if c.strip():
                        self.blocks.append(Block("table-cell", no, c.strip(), [(0, no)]))
                continue
            lm = LIST_RE.match(line)
            if lm:
                self.start("list-item", no, lm.group(3))
                continue
            if stripped.startswith(">"):
                stripped = stripped.lstrip("> ").strip()
            if self.cur is not None and self.cur.kind in ("paragraph", "list-item"):
                self.cur_parts.append((no, clean_md(stripped)))
            else:
                self.start("paragraph", no, stripped)
        self.flush()
        return self.blocks


def split_cells(row: str) -> list[str]:
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    cells, cur, in_code = [], "", False
    i = 0
    while i < len(row):
        c = row[i]
        if c == "\\" and i + 1 < len(row) and row[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if c == "`":
            in_code = not in_code
        if c == "|" and not in_code:
            cells.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    cells.append(cur)
    return cells


@dataclass
class _Frame:
    kind: str
    line: int
    buf: list[str] = field(default_factory=list)
    blocked: int = 0


class HtmlCollector(HTMLParser):
    KIND = {"h1": "heading", "h2": "heading", "h3": "heading", "h4": "heading", "h5": "heading",
            "h6": "heading", "p": "paragraph", "li": "list-item", "td": "table-cell", "th": "table-cell",
            "dt": "list-item", "dd": "list-item"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self.stack: list[tuple[str, list[_Frame], list[_Frame]]] = []  # (tag, 開いた枠, 止めた枠)
        self.frames: list[_Frame] = []
        self.skip = 0
        self.disabled = False
        self.profile: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            if tag == "br":
                self._data(" ")
            return
        if tag in SKIP_TAGS:
            self.skip += 1
        line = self.getpos()[0]
        opened: list[_Frame] = []
        blocked: list[_Frame] = []
        if not self.skip:
            kind = self.KIND.get(tag)
            if kind:
                opened.append(_Frame(kind, line))
            cls = dict(attrs).get("class") or ""
            if CARD_CLASS_RE.search(cls):
                opened.append(_Frame("card", line))
            if tag in ("ul", "ol", "dl", "table"):
                # 入れ子の箇条や表は、外側の項目やセルの長さに数えない
                blocked = [f for f in self.frames if f.kind in ("list-item", "table-cell", "paragraph")]
                for f in blocked:
                    f.blocked += 1
        self.frames.extend(opened)
        self.stack.append((tag, opened, blocked))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not any(t == tag for t, _, _ in self.stack):
            return
        while self.stack:
            t, opened, blocked = self.stack.pop()
            if t in SKIP_TAGS:
                self.skip -= 1
            for f in blocked:
                f.blocked -= 1
            for f in opened:
                self.frames.remove(f)
                text = SPACE_RE.sub(" ", "".join(f.buf)).strip()
                if text and not self.disabled:
                    self.blocks.append(Block(f.kind, f.line, text, [(0, f.line)]))
            if t == tag:
                break

    def handle_comment(self, data):
        pm = PROFILE_RE.search(data)
        if pm:
            self.profile = pm.group(1)
        if DISABLE in data:
            self.disabled = True
        elif ENABLE in data:
            self.disabled = False

    def handle_data(self, data):
        self._data(data)

    def _data(self, data):
        if self.skip:
            return
        for f in self.frames:
            if not f.blocked:
                f.buf.append(data)

    def parse(self, text: str) -> list[Block]:
        self.feed(text)
        self.close()
        while self.stack:  # 閉じ忘れの要素
            self.handle_endtag(self.stack[-1][0])
        self.blocks.sort(key=lambda b: b.line)
        return self.blocks


# ---- 測る ----------------------------------------------------------------

def short(s: str, n: int = 60) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n] + "…"


def measure(blocks: list[Block], limits: list[Limit], profile: str, path: str) -> list[dict]:
    out: list[dict] = []
    by_target: dict[str, list[Limit]] = {}
    for lim in limits:
        by_target.setdefault(lim.target, []).append(lim)

    def judge(lim: Limit, value: int, line: int, text: str) -> None:
        info, warn = lim.thresholds(profile)
        if value <= info:
            return
        sev = "warn" if value > warn else "info"
        unit = "字" if lim.measure == "chars" else "文"
        limit = warn if sev == "warn" else info
        out.append({
            "skill": "tsumekomi",
            "id": lim.id,
            "path": path,
            "line": line,
            "severity": sev,
            "text": short(text),
            "message": f"{lim.label}が {value}{unit}（目安 {info}{unit}）。{lim.why}",
            "measured": value,
            "limit": limit,
            "hint": lim.hint,
            "keep_when": lim.keep_when,
        })

    for b in blocks:
        if not is_japanese(b.text):
            continue
        for lim in by_target.get(b.kind, []):
            if lim.measure == "chars":
                judge(lim, count_chars(b.text), b.line, b.text)
            elif lim.measure == "sentences":
                judge(lim, len(split_sentences(b.text)), b.line, b.text)
        if b.kind in ("paragraph", "list-item"):
            for lim in by_target.get("sentence", []):
                for pos, sent in split_sentences(b.text):
                    if is_japanese(sent):
                        judge(lim, count_chars(sent), b.line_at(pos), sent)
    out.sort(key=lambda f: (f["path"], f["line"]))
    return out


def scan(text: str, kind: str, path: str, profile: str | None = None,
         limits: list[Limit] | None = None) -> list[dict]:
    if limits is None:
        limits, _ = load_limits()
    collector = HtmlCollector() if kind == "html" else MdCollector()
    blocks = collector.parse(text)
    return measure(blocks, limits, profile or collector.profile or "default", path)


def kind_of(path: Path) -> str:
    return "html" if path.suffix.lower() in (".html", ".htm") else "md"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--stdin", action="store_true", help="標準入力から読む")
    ap.add_argument("--type", choices=["md", "html"], default="md", help="--stdin のときの形式")
    ap.add_argument("--profile", help="目安の種類（limits.yaml の profiles）。既定は文書の指定か default")
    ap.add_argument("--format", choices=["text", "findings"], default="text")
    ap.add_argument("--severity", choices=["info", "warn"], default="info", help="この重さ以上だけ出す")
    ap.add_argument("--fail-on", choices=["none", "info", "warn"], default="none")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    if not args.files and not args.stdin:
        ap.error("ファイルを指定するか --stdin を付けてください")
    limits, profiles = load_limits()
    if args.profile and args.profile not in profiles:
        ap.error(f"profile は {', '.join(profiles)} のどれか")

    found: list[dict] = []
    if args.stdin:
        found += scan(sys.stdin.read(), args.type, "<stdin>", args.profile, limits)
    for f in args.files:
        if not f.is_file():
            print(f"見つかりません: {f}", file=sys.stderr)
            return 2
        found += scan(f.read_text(encoding="utf-8"), kind_of(f), str(f), args.profile, limits)

    rank = {"info": 0, "warn": 1}
    found = [x for x in found if rank[x["severity"]] >= rank[args.severity]]

    if args.format == "findings":
        json.dump({"findings": found}, sys.stdout, ensure_ascii=False, indent=2)
        print()
    elif not found:
        print("指摘なし")
    else:
        warn = sum(1 for x in found if x["severity"] == "warn")
        print(f"指摘 {len(found)} 件（warn {warn} / info {len(found) - warn}）\n")
        for x in found:
            print(f"{x['path']}:{x['line']} [{x['severity']}] {x['id']}: {x['message']}")
            print(f"  箇所: {x['text']}")
            print(f"  書き換え方の例: {' / '.join(x['hint'])}（残してもよい）")
            print()

    if args.fail_on != "none" and any(rank[x["severity"]] >= rank[args.fail_on] for x in found):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
