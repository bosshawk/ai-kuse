"""実行: uv run --with pytest --with pyyaml --with jsonschema pytest -q"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import kumihan  # noqa: E402

JA = "<p>グループ名を押すと、編集欄の上にポップオーバーを開きます。</p>"


def ids(html: str) -> list[str]:
    return [f.id for f in kumihan.check(html, "t.html")]


def test_english_page_is_left_alone():
    html = "<html><body><p>Hello world, this is an English page.</p></body></html>"
    assert ids(html) == []
    assert kumihan.fix(html) == (html, [])


def test_missing_lang_and_css():
    assert ids(f"<main>{JA}</main>") == ["no-lang", "no-base-css"]


def test_fix_adds_lang_to_html_first():
    html = f"<html><head><title>t</title></head><body>{JA}</body></html>"
    new, done = kumihan.fix(html)
    assert '<html lang="ja">' in new
    assert "<body>" in new  # body には足さない
    assert kumihan.MARKER in new
    assert new.index(kumihan.MARKER) > new.index("<head>")
    assert len(done) == 2
    assert ids(new) == []


def test_fix_on_fragment_uses_main_and_title():
    html = f"<title>t</title>\n<style>p{{margin:0}}</style>\n<main>{JA}</main>"
    new, _ = kumihan.fix(html)
    assert '<main lang="ja">' in new
    assert new.index(kumihan.MARKER) > new.index("</title>")
    assert ids(new) == []


def test_fix_is_idempotent():
    new, _ = kumihan.fix(f"<main>{JA}</main>")
    again, done = kumihan.fix(new)
    assert again == new and done == []


def test_other_language_is_not_overwritten():
    html = f'<html lang="en"><body>{JA}</body></html>'
    assert "lang-mismatch" in ids(html)
    new, _ = kumihan.fix(html)
    assert '<html lang="en">' in new and not kumihan.has_lang_ja(new)
    assert new.index("<html") < new.index(kumihan.MARKER)  # CSS は <html> の外に出さない


def test_manual_br_in_middle_of_sentence():
    html = f'<main lang="ja">{JA}<p>上に検索欄と<br>グループを表示します。</p></main>'
    found = kumihan.check(html, "t.html")
    assert [f.id for f in found if f.id == "manual-br"] == ["manual-br"]


def test_br_after_period_is_fine():
    html = f'<main lang="ja">{JA}<p>開きます。<br>次に表示します。</p></main>'
    assert "manual-br" not in ids(html)


def test_old_css_is_replaced():
    v1 = '<style data-kumihan="ja-base">\n/* kumihan:ja-base v1 */\n:where([lang|="ja"]) { word-break: auto-phrase; }\n</style>\n'
    html = f"<html lang=\"ja\"><head>\n{v1}</head><body>{JA}</body></html>"
    assert ids(html) == ["old-base-css"]
    new, done = kumihan.fix(html)
    assert "kumihan:ja-base v1" not in new and new.count(kumihan.MARKER) == 1
    assert done and ids(new) == []


def test_body_text_is_not_phrase_wrapped():
    css = kumihan.CSS_PATH.read_text(encoding="utf-8")
    base = css.split("}")[0]  # [lang|="ja"] 全体への指定
    assert "auto-phrase" not in base
    assert '[data-kumihan~="phrase"]' in css


def test_ch_width_becomes_ic():
    html = (f'<main lang="ja"><style>.lead{{max-width:68ch;columns:2 20ch}} pre{{width: 80.5ch}}</style>'
            f'<p class="lead" style="max-inline-size: 40ch">{JA}</p><p>max-width: 68ch と本文に書いた例</p></main>')
    assert ids(html).count("ch-width") == 3
    new, done = kumihan.fix(html)
    assert ".lead{columns:2 20ch}" in new  # 上限は消す
    assert 'style=""' in new
    assert "width: 80.5ic" in new  # width は消さずに ic にする
    assert "columns:2 20ch" in new  # 幅のプロパティ以外は変えない
    assert "max-width: 68ch と本文に書いた例" in new  # 本文の文字は変えない
    assert "ch-width" not in ids(new)
    assert kumihan.fix(new) == (new, [])


def test_ch_width_in_base_css_is_ignored():
    new, _ = kumihan.fix(f"<main>{JA}</main>")
    assert "ch-width" not in ids(new)
