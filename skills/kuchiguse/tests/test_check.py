"""実行: uv run --with pytest --with pyyaml --with jsonschema pytest -q"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check  # noqa: E402
import validate  # noqa: E402
from ai_kuse_core import load_terms, scan  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def terms():
    return load_terms()


def test_terms_are_valid():
    assert validate.validate(sorted((ROOT / "terms").glob("*.yaml"))) == []


def test_should_not_hit(terms):
    hits = scan((FIX / "should_not_hit.md").read_text(encoding="utf-8"), terms)
    assert [(h.line, h.matched, h.term.id) for h in hits] == []


def test_should_hit(terms):
    hits = scan((FIX / "should_hit.md").read_text(encoding="utf-8"), terms)
    found = [(h.line, h.term.id) for h in hits]
    assert found == [
        (3, "setsu"),
        (5, "shohon"),
        (5, "daicho"),
        (6, "nigiru"),
        (6, "chakuchi"),
        (7, "haikan"),
        (7, "tanpo"),
        (8, "otoshiana"),
        (8, "kandokoro"),
    ]


def test_column_is_character_based(terms):
    hits = scan("設定は正本とする。", terms)
    assert [(h.col, h.matched) for h in hits] == [(4, "正本")]


def test_quoted_flag(terms):
    hits = scan("通達には「品質を担保する」とある。品質を担保する。", terms)
    assert [(h.matched, h.quoted) for h in hits] == [("担保", True), ("担保", False)]


def test_allow_by_id_and_term(terms):
    text = "正本と台帳を見る。"
    assert {h.term.id for h in scan(text, terms, allow={"shohon"})} == {"daicho"}
    assert {h.term.id for h in scan(text, terms, allow={"台帳"})} == {"shohon"}


def test_cli_json_and_fail_on(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)  # git の外で動かし、ほかの allow.txt を読まない
    f = tmp_path / "a.md"
    f.write_text("よくある落とし穴。\n", encoding="utf-8")
    assert check.main([str(f), "--format", "json", "--fail-on", "warn"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1
    assert out["hits"][0]["id"] == "otoshiana"
    assert out["hits"][0]["suggest"]


def test_project_allow_file(tmp_path, capsys, monkeypatch):
    (tmp_path / ".ai-kuse").mkdir()
    (tmp_path / ".ai-kuse" / "allow.txt").write_text("# このプロジェクトでは使う\notoshiana\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    f = tmp_path / "a.md"
    f.write_text("よくある落とし穴。\n", encoding="utf-8")
    assert check.main([str(f), "--fail-on", "info"]) == 0
    assert "指摘なし" in capsys.readouterr().out


LOCAL_TERMS = """version: 1
domain: local
categories:
  local: 利用者が足したワード
terms:
  - id: local-kuse
    term: ほげ語
    category: local
    severity: warn
    match:
      literal: [ほげ語]
    why: テスト用のワード。
    suggest: [ふつうの語]
    examples:
      - bad: ここでほげ語を使う。
        good: ここでふつうの語を使う。
"""


@pytest.mark.parametrize("where", ["project", "user"])
def test_user_added_terms_are_loaded(tmp_path, capsys, monkeypatch, where):
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.setenv("AI_KUSE_HOME", str(home))
    target = (proj / ".ai-kuse" / "terms") if where == "project" else (home / "terms")
    target.mkdir(parents=True)
    (target / "local.yaml").write_text(LOCAL_TERMS, encoding="utf-8")
    assert validate.validate([target / "local.yaml"]) == []
    monkeypatch.chdir(proj)
    f = proj / "a.md"
    f.write_text("ここでほげ語を使う。\n", encoding="utf-8")
    assert check.main([str(f), "--format", "json"]) == 0
    ids = [h["id"] for h in json.loads(capsys.readouterr().out)["hits"]]
    assert "local-kuse" in ids
