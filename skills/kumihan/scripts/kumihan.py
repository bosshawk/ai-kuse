#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""日本語の HTML の組版（折り返しと禁則）を調べ、直せるものはスクリプトで直す。

使い方:
  uv run --script scripts/kumihan.py check page.html
  uv run --script scripts/kumihan.py fix page.html          # lang="ja" と組版CSSを入れる
  uv run --script scripts/kumihan.py check --format findings page.html

見るもの:
  no-lang      日本語の本文があるのに lang="ja" がない（fix で直る）
  lang-mismatch  <html lang="en"> などで、日本語の要素に lang="ja" がない（手で直す）
  no-base-css  組版CSS（assets/ja-base.css）が入っていない（fix で直る）
  manual-br    文の途中で <br> を入れて手で改行している（手で直す）

日本語の本文がない HTML は何もしない。色・フォント・レイアウトには触れない。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CSS_PATH = SKILL_DIR / "assets" / "ja-base.css"
MARKER = "kumihan:ja-base"

KANA_RE = re.compile(r"[ぁ-ゖァ-ヺ]")
JA_CHAR = r"[ぁ-ゖァ-ヺー一-鿿々、]"
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
LANG_JA_RE = re.compile(r"""\blang\s*=\s*["']?ja\b""", re.I)
OPEN_TAG_RE = {name: re.compile(rf"<{name}\b[^>]*>", re.I) for name in ("html", "head", "body", "main")}
LANG_ATTR_RE = re.compile(r"""\blang\s*=\s*["']?([A-Za-z-]+)""", re.I)
TITLE_END_RE = re.compile(r"</title\s*>", re.I)
BR_RE = re.compile(rf"(?<={JA_CHAR})\s*<br\s*/?>\s*(?={JA_CHAR})", re.I)

MIN_KANA = 10  # これより仮名が少なければ日本語のページとみなさない


@dataclass
class Finding:
    id: str
    path: str
    line: int
    severity: str
    text: str
    message: str
    hint: list[str] = field(default_factory=list)
    fixable: bool = False

    def to_dict(self) -> dict:
        return {
            "skill": "kumihan",
            "id": self.id,
            "path": self.path,
            "line": self.line,
            "severity": self.severity,
            "text": self.text,
            "message": self.message,
            "hint": self.hint,
            "fixable": self.fixable,
        }


def visible_text(html: str) -> str:
    return TAG_RE.sub(" ", SCRIPT_STYLE_RE.sub(" ", html))


def has_lang_ja(html: str) -> bool:
    """<style> や <script> の中（CSS のコメントなど）は数えない。"""
    return bool(LANG_JA_RE.search(SCRIPT_STYLE_RE.sub(" ", html)))


def is_japanese(html: str) -> bool:
    return len(KANA_RE.findall(visible_text(html))) >= MIN_KANA


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def lang_target(html: str) -> re.Match | None:
    """lang="ja" を足せる最初の開きタグ（html → body → main の順）。lang がすでにあるタグは選ばない。"""
    for name in ("html", "body", "main"):
        m = OPEN_TAG_RE[name].search(html)
        if m and not LANG_ATTR_RE.search(m.group(0)):
            return m
        if m and name == "html":
            # <html lang="en"> のように別の言語が書いてあるときは、勝手に変えない
            return None
    return None


def check(html: str, path: str) -> list[Finding]:
    if not is_japanese(html):
        return []
    out: list[Finding] = []
    if not has_lang_ja(html):
        target = lang_target(html)
        html_tag = OPEN_TAG_RE["html"].search(html)
        other = LANG_ATTR_RE.search(html_tag.group(0)) if html_tag else None
        if other and not other.group(1).lower().startswith("ja"):
            out.append(Finding(
                "lang-mismatch", path, line_of(html, html_tag.start()), "warn", html_tag.group(0),
                f'<html lang="{other.group(1)}"> のまま日本語を書いている。文節の折り返しが効かない',
                ['<html lang="ja"> に変える', '日本語の部分を包む要素に lang="ja" を付ける'],
            ))
        else:
            out.append(Finding(
                "no-lang", path, line_of(html, target.start()) if target else 0, "warn",
                target.group(0) if target else "",
                'lang="ja" がない。文節の折り返しと日本語の禁則が効かない',
                ['本文を包む要素に lang="ja" を付ける'], fixable=target is not None,
            ))
    if MARKER not in html:
        out.append(Finding(
            "no-base-css", path, 0, "warn", "",
            "組版CSS（ja-base.css）が入っていない。語の途中で折り返す",
            ["kumihan fix で入れる"], fixable=True,
        ))
    for m in BR_RE.finditer(html):
        start = max(0, m.start() - 20)
        snippet = re.sub(r"\s+", " ", html[start:m.end() + 20]).strip()
        out.append(Finding(
            "manual-br", path, line_of(html, m.start()), "info", snippet,
            "文の途中を <br> で改行している。画面の幅が変わると変な位置で折れる",
            ["<br> を消して折り返しに任せる", "別の文や項目に分ける"],
        ))
    return out


def style_block() -> str:
    css = CSS_PATH.read_text(encoding="utf-8").strip()
    return f'<style data-kumihan="ja-base">\n{css}\n</style>\n'


def fix(html: str) -> tuple[str, list[str]]:
    """直せるもの（no-lang, no-base-css）だけを直す。直した内容の説明を返す。"""
    if not is_japanese(html):
        return html, []
    done: list[str] = []
    if not has_lang_ja(html):
        target = lang_target(html)
        if target:
            tag = target.group(0)
            new_tag = tag[:-1].rstrip("/").rstrip() + ' lang="ja"' + ("/>" if tag.endswith("/>") else ">")
            html = html[:target.start()] + new_tag + html[target.end():]
            done.append(f'lang="ja" を {tag.split()[0].rstrip(">")}> に付けた')
    if MARKER not in html:
        block = style_block()
        # 入れる場所: <head> の直後 → </title> の後 → <html> の直後 → 先頭
        anchor = (OPEN_TAG_RE["head"].search(html) or TITLE_END_RE.search(html)
                  or OPEN_TAG_RE["html"].search(html))
        if anchor:
            pos = anchor.end()
            block = "\n" + block
        else:
            pos = 0
        html = html[:pos] + block + html[pos:]
        done.append("組版CSS（ja-base.css）を入れた")
    return html, done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["check", "fix"])
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--format", choices=["text", "findings"], default="text")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # Windows の既定（cp932）で文字化けしないように

    findings: list[Finding] = []
    for f in args.files:
        if not f.is_file():
            print(f"見つかりません: {f}", file=sys.stderr)
            return 2
        if f.suffix.lower() not in (".html", ".htm"):
            continue
        html = f.read_text(encoding="utf-8")
        if args.command == "fix":
            new, done = fix(html)
            if new != html:
                f.write_text(new, encoding="utf-8", newline="")
            for d in done:
                print(f"{f}: {d}", file=sys.stderr if args.format == "findings" else sys.stdout)
            html = new
        findings += check(html, str(f))

    if args.format == "findings":
        json.dump({"findings": [x.to_dict() for x in findings]}, sys.stdout, ensure_ascii=False, indent=2)
        print()
    elif not findings:
        print("指摘なし")
    else:
        for x in findings:
            mark = "（fix で直る）" if x.fixable else ""
            print(f"{x.path}:{x.line} [{x.severity}] {x.id}{mark}: {x.message}")
            if x.text:
                print(f"  箇所: {x.text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
