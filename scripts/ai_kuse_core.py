"""ai-kuse の共通処理: 語の一覧の読み込みと、本文からの検出。

check.py と validate.py から import する。PyYAML は呼び出し側のスクリプトが PEP 723 で宣言する。
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TERMS_DIR = REPO_ROOT / "terms"
SCHEMA_PATH = REPO_ROOT / "schema" / "terms.schema.json"

# 1行だけ検査から外す印と、範囲を外す印（Markdown のコメント）
IGNORE_LINE = "ai-kuse-ignore"
DISABLE = "ai-kuse-disable"
ENABLE = "ai-kuse-enable"

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
URL_RE = re.compile(r"https?://\S+")
QUOTE_RE = re.compile(r"「[^「」]*」|『[^『』]*』|“[^“”]*”|\"[^\"]*\"")


@dataclass
class Term:
    id: str
    term: str
    category: str
    category_label: str
    severity: str
    domain: str
    why: str
    suggest: list[str]
    keep_when: list[str]
    examples: list[dict]
    patterns: list[re.Pattern] = field(default_factory=list)
    excludes: list[re.Pattern] = field(default_factory=list)


@dataclass
class Hit:
    path: str
    line: int
    col: int  # 1 始まり、文字数で数える
    matched: str
    text: str
    term: Term
    quoted: bool = False  # カギ括弧や引用符の中で当たった（引用なら直さない）

    def to_dict(self) -> dict:
        t = self.term
        return {
            "path": self.path,
            "line": self.line,
            "col": self.col,
            "matched": self.matched,
            "quoted": self.quoted,
            "text": self.text,
            "id": t.id,
            "term": t.term,
            "domain": t.domain,
            "category": t.category,
            "category_label": t.category_label,
            "severity": t.severity,
            "why": t.why,
            "suggest": t.suggest,
            "keep_when": t.keep_when,
        }


def load_raw(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def terms_files(domains: list[str] | None = None) -> list[Path]:
    files = sorted(TERMS_DIR.glob("*.yaml"))
    if domains:
        files = [p for p in files if p.stem in domains]
    return files


def compile_term(raw: dict, domain: str, categories: dict) -> Term:
    m = raw["match"]
    patterns = [re.compile(re.escape(s)) for s in m.get("literal", [])]
    patterns += [re.compile(s) for s in m.get("regex", [])]
    excludes = [re.compile(re.escape(s)) for s in m.get("exclude", [])]
    excludes += [re.compile(s) for s in m.get("exclude_regex", [])]
    return Term(
        id=raw["id"],
        term=raw["term"],
        category=raw["category"],
        category_label=categories.get(raw["category"], raw["category"]),
        severity=raw["severity"],
        domain=domain,
        why=raw["why"],
        suggest=list(raw.get("suggest", [])),
        keep_when=list(raw.get("keep_when", []) or []),
        examples=list(raw.get("examples", [])),
        patterns=patterns,
        excludes=excludes,
    )


def load_terms(domains: list[str] | None = None) -> list[Term]:
    terms: list[Term] = []
    for path in terms_files(domains):
        data = load_raw(path)
        cats = data.get("categories", {})
        for raw in data.get("terms", []):
            terms.append(compile_term(raw, data["domain"], cats))
    return terms


def git_root(start: Path) -> Path:
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return start


def load_allow(start: Path, extra: Path | None = None) -> set[str]:
    """プロジェクトで直さない語。.ai-kuse/allow.txt に、1行に id か語を書く。"""
    allow: set[str] = set()
    candidates = [git_root(start) / ".ai-kuse" / "allow.txt"]
    if extra:
        candidates.append(extra)
    for p in candidates:
        if p.is_file():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.split("#", 1)[0].strip()
                if line:
                    allow.add(line)
    return allow


def _mask(text: str, pattern: re.Pattern) -> str:
    """当たった範囲を全角スペースで伏せる（列の位置は保つ）。"""
    return pattern.sub(lambda m: "　" * len(m.group(0)), text)


def visible_lines(text: str):
    """検査する行を (行番号, 伏せたあとの行, 元の行) で返す。コードブロック、インラインコード、URL、印のある行は見ない。"""
    in_fence = None
    disabled = False
    for no, line in enumerate(text.splitlines(), start=1):
        fm = FENCE_RE.match(line)
        if in_fence:
            if fm and fm.group(1)[0] == in_fence[0] and len(fm.group(1)) >= len(in_fence):
                in_fence = None
            continue
        if fm:
            in_fence = fm.group(1)
            continue
        if DISABLE in line:
            disabled = True
            continue
        if ENABLE in line:
            disabled = False
            continue
        if disabled or IGNORE_LINE in line:
            continue
        masked = _mask(_mask(line, INLINE_CODE_RE), URL_RE)
        yield no, masked, line


def find_in_line(line: str, term: Term) -> list[tuple[int, str]]:
    """1行の中で term に当たった (列の位置 0 始まり, 当たった文字列)。除外語と重なる当たりは捨てる。"""
    ex_spans = [m.span() for ex in term.excludes for m in ex.finditer(line)]
    found: dict[int, str] = {}
    for pat in term.patterns:
        for m in pat.finditer(line):
            s, e = m.span()
            if s == e:
                continue
            if any(s < xe and xs < e for xs, xe in ex_spans):
                continue
            found.setdefault(s, m.group(0))
    # 同じ語の別のパターンが重なって当たったとき（「この節では」）は、先に始まる1件だけを残す
    result: list[tuple[int, str]] = []
    for s, text in sorted(found.items()):
        if result and s < result[-1][0] + len(result[-1][1]):
            continue
        result.append((s, text))
    return result


def scan(text: str, terms: list[Term], path: str = "<stdin>", allow: set[str] | None = None) -> list[Hit]:
    allow = allow or set()
    active = [t for t in terms if t.id not in allow and t.term not in allow]
    hits: list[Hit] = []
    for no, masked, original in visible_lines(text):
        quotes = [m.span() for m in QUOTE_RE.finditer(masked)]
        for t in active:
            for col, matched in find_in_line(masked, t):
                end = col + len(matched)
                quoted = any(qs < col and end < qe for qs, qe in quotes)
                hits.append(Hit(path, no, col + 1, matched, original, t, quoted))
    hits.sort(key=lambda h: (h.path, h.line, h.col))
    return hits
