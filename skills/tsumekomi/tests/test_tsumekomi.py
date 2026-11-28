"""実行: uv run --with pytest --with pyyaml --with jsonschema pytest -q"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import tsumekomi  # noqa: E402

LONG_CELL = "セルに説明文を入れると列で見比べられなくなるので短い語にしてから注記に移すとよいです"  # 40字超


@pytest.fixture(scope="module")
def limits():
    return tsumekomi.load_limits()[0]


def ids(text, limits, kind="md", profile=None):
    return [(f["id"], f["severity"]) for f in tsumekomi.scan(text, kind, "t", profile, limits)]


def test_limits_file_is_consistent(limits):
    targets = {"heading", "sentence", "list-item", "table-cell", "card", "paragraph"}
    for lim in limits:
        assert lim.target in targets, lim.id
        assert lim.measure in ("chars", "sentences"), lim.id
        assert lim.info < lim.warn, lim.id
        assert lim.why and lim.hint, lim.id


def test_short_document_has_no_findings(limits):
    md = "# 結論\n\n短い文です。読みやすいです。\n\n- 項目です\n- 次の項目です\n\n| 案 | 手間 |\n|---|---|\n| A | 小 |\n"
    assert ids(md, limits) == []


def test_long_table_cell(limits):
    md = f"| 案 | 説明 |\n|---|---|\n| A | {LONG_CELL} |\n"
    assert ("table-cell", "info") in ids(md, limits)


def test_reference_profile_relaxes_cells(limits):
    md = f"| 案 | 説明 |\n|---|---|\n| A | {LONG_CELL} |\n"
    assert ids(md, limits, profile="reference") == []
    assert ids("<!-- tsumekomi: profile=reference -->\n" + md, limits) == []


def test_list_item_with_many_sentences(limits):
    md = "- 結果を返す。数値を書く。違いを書く。足すかを書く。\n"
    assert ("list-item-sentences", "warn") in ids(md, limits)


def test_wrapped_lines_join_into_one_item(limits):
    md = "- これは折り返された\n  箇条書きの項目です。\n"
    blocks = tsumekomi.MdCollector().parse(md)
    assert [b.text for b in blocks] == ["これは折り返された箇条書きの項目です。"]


def test_quote_brackets_do_not_split_sentences():
    s = "「設定はこれを基準にする。」と書いた。次の文です。"
    assert len(tsumekomi.split_sentences(s)) == 2


def test_code_and_english_are_not_measured(limits):
    md = "```\n" + "これはコードの中なので測らない。" * 20 + "\n```\n\n" + "This is English. " * 20 + "\n"
    assert ids(md, limits) == []


def test_ignore_markers(limits):
    long_sentence = "長い文" * 50 + "です。"
    md = f"<!-- tsumekomi-disable -->\n{long_sentence}\n<!-- tsumekomi-enable -->\n\n{long_sentence} <!-- tsumekomi-ignore -->\n"
    assert ids(md, limits) == []


def test_html_cells_cards_and_nested_lists(limits):
    html = f"""
    <table><tr><td>{LONG_CELL}</td></tr></table>
    <div class="plan card">{"カードの本文です。" * 20}</div>
    <ul><li>親の項目です<ul><li>{"子の項目は親に数えない。" * 3}</li></ul></li></ul>
    """
    found = tsumekomi.scan(html, "html", "t.html", None, limits)
    got = {(f["id"], f["line"]) for f in found}
    assert ("table-cell", 2) in got
    assert ("card", 3) in got
    # 親の li は短いので指摘されない（子の li の文が混ざらない）
    assert not [f for f in found if f["id"] == "list-item" and f["text"].startswith("親")]


def test_sentence_line_numbers_follow_wrapped_lines(limits):
    md = "最初の短い文です。\n" + "とても長い文" * 20 + "です。\n"
    found = [f for f in tsumekomi.scan(md, "md", "t", None, limits) if f["id"] == "sentence"]
    assert found and found[0]["line"] == 2
