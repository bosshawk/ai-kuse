#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""段落の形（1段落の文の数・字数、1文だけの段落の連続）を、AI の文章と人の文章で比べる。

文章群は kuchiguse の survey.py prepare が作ったものを使う（~/.cache/ai-kuse）。
  ai      Claude Code の会話ログにある Claude の返答と、Claude が Write した .md（生の Markdown）
  human   Qiita の記事（2019〜2021 年、ストック 20 以上）
  recent  Qiita の記事（今年、ストック 20 以上）
段落の切り方は tsumekomi.py の Markdown の読み方と同じ（空行で段落を分ける）。

使い方: uv run --script measure.py > ../results/paragraph_shape.json
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SKILLS = HERE.parents[3].parent  # skills/
sys.path.insert(0, str(SKILLS / "tsumekomi" / "scripts"))
sys.path.insert(0, str(SKILLS / "kuchiguse" / "scripts"))
import tsumekomi  # noqa: E402
import survey  # noqa: E402

DATA = Path(os.environ.get("AI_KUSE_DATA", Path.home() / ".cache" / "ai-kuse"))
MIN_JA = 300  # これより日本語が短い文章は段落の形を見られないので外す


def qiita(prefix: str) -> list[str]:
    out = []
    for f in sorted((DATA / "qiita").glob(f"{prefix}_*.json")):
        out += [it["body"] for it in json.loads(f.read_text(encoding="utf-8"))]
    return out


def shape(text: str) -> dict | None:
    blocks = tsumekomi.MdCollector().parse(text)
    ja = sum(len(survey.JA.findall(b.text)) for b in blocks)
    if ja < MIN_JA:
        return None
    paras, runs, run, lines = [], [], 0, []
    for b in blocks:
        if b.kind == "paragraph" and tsumekomi.is_japanese(b.text):
            n = len(tsumekomi.split_sentences(b.text))
            paras.append((n, tsumekomi.count_chars(b.text)))
            # 段落の中の改行（空行でない改行）。Qiita や GitHub のコメントでは見た目の改行になる
            cuts = [pos for pos, _ in b.line_starts] + [len(b.text)]
            for a, z in zip(cuts, cuts[1:]):
                seg = b.text[a:z]
                if tsumekomi.is_japanese(seg):
                    lines.append((len(tsumekomi.split_sentences(seg)), tsumekomi.count_chars(seg),
                                  seg.rstrip().endswith(tuple("。！？!?」）)")), n > 1 and len(cuts) > 2))
            run = run + 1 if n == 1 else 0
            if run:
                runs.append(run)
            continue
        run = 0  # 見出し・箇条・表・コードをはさんだら連続は切れる
    return {"ja": ja, "paras": paras, "max_run": max(runs, default=0), "lines": lines}


def summarize(shapes: list[dict]) -> dict:
    paras = [p for s in shapes for p in s["paras"]]
    sents = [n for n, _ in paras]
    chars = sorted(c for _, c in paras)
    total = len(paras) or 1
    def share(pred):
        return round(100 * sum(1 for n in sents if pred(n)) / total, 1)
    docs = len(shapes)
    def docs_with_run(k):
        return round(100 * sum(1 for s in shapes if s["max_run"] >= k) / docs, 1)
    return {
        "docs": docs,
        "paragraphs": len(paras),
        "sentences_per_paragraph_%": {"1": share(lambda n: n == 1), "2": share(lambda n: n == 2),
                                      "3": share(lambda n: n == 3), "4": share(lambda n: n == 4),
                                      "5": share(lambda n: n == 5), "6+": share(lambda n: n >= 6)},
        "paragraphs_over_%": {"120字": round(100 * sum(1 for c in chars if c > 120) / total, 1),
                              "200字": round(100 * sum(1 for c in chars if c > 200) / total, 1),
                              "4文以上": share(lambda n: n >= 4), "6文以上": share(lambda n: n >= 6)},
        "chars_per_paragraph": {"median": statistics.median(chars),
                                "p90": chars[int(len(chars) * 0.9)], "p99": chars[int(len(chars) * 0.99)]},
        "source_lines": line_stats([l for s in shapes for l in s["lines"]]),
        "docs_with_one_sentence_run_%": {f">={k}": docs_with_run(k) for k in (2, 3, 4, 5, 6, 8)},
    }


def line_stats(lines: list[tuple]) -> dict:
    """段落の中の1行（改行から改行まで）の形。複数文の段落を行で区切っている割合も出す。"""
    multi = [l for l in lines if l[3]]  # 2文以上の段落を、2行以上で書いている行
    chars = sorted(c for _, c, _, _ in lines)
    return {
        "lines": len(lines),
        "chars_median": statistics.median(chars) if chars else 0,
        "chars_p90": chars[int(len(chars) * 0.9)] if chars else 0,
        "ends_with_sentence_end_%": round(100 * sum(1 for l in lines if l[2]) / (len(lines) or 1), 1),
        "one_sentence_per_line_%": round(100 * sum(1 for l in lines if l[0] == 1) / (len(lines) or 1), 1),
        "lines_in_multi_sentence_paragraphs_written_on_several_lines": len(multi),
    }


def main() -> None:
    corpora = {
        "ai": [t for _, t in survey._ai_docs(set())],
        "human": qiita("human"),
        "recent": qiita(f"recent{__import__('datetime').date.today().year}"),
    }
    result = {}
    for name, texts in corpora.items():
        shapes = [s for s in map(shape, texts) if s]
        result[name] = summarize(shapes)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
