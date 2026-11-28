"""スキルをまたいだテスト（共通の指摘の形、naoshi、hook）。

実行: uv run --with pytest --with pyyaml --with jsonschema pytest -q
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((REPO / "shared" / "finding.schema.json").read_text(encoding="utf-8"))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


naoshi = load("test_naoshi_mod", REPO / "skills" / "naoshi" / "scripts" / "naoshi.py")
hook = load("test_hook_mod", REPO / "hooks" / "post_write.py")

MD = """# 設計

設定はこの YAML を正本とする。

| 案 | 説明 |
|---|---|
| A | セルに説明文を入れると列で見比べられなくなるので短い語にしてから注記に移すとよいですし、ほかにも書くことがたくさんあります |
"""

HTML = "<title>t</title>\n<main><p>グループ名を押すと、編集欄の上にポップオーバーを開きます。</p></main>\n"


@pytest.fixture()
def files(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text(MD, encoding="utf-8")
    html = tmp_path / "page.html"
    html.write_text(HTML, encoding="utf-8")
    return md, html


def test_all_skills_are_found():
    assert naoshi.Checkers().available() == ["kumihan", "tsumekomi", "ai-kuse"]


def test_findings_follow_shared_schema(files):
    ck = naoshi.Checkers()
    found = []
    for f in files:
        found += ck.check(f)
    skills = {f["skill"] for f in found}
    assert skills == {"kumihan", "tsumekomi", "ai-kuse"}
    jsonschema.validate({"findings": found}, SCHEMA)


def test_ai_kuse_cli_findings_format(files, capsys):
    sys.path.insert(0, str(REPO / "skills" / "ai-kuse" / "scripts"))
    import check  # noqa: PLC0415

    check.main(["--format", "findings", str(files[0])])
    data = json.loads(capsys.readouterr().out)
    jsonschema.validate(data, SCHEMA)
    assert any(f["id"] for f in data["findings"])


def test_sort_puts_structure_before_words(files):
    found = naoshi.sort_findings(naoshi.Checkers().check(files[0]))
    order = [f["skill"] for f in found]
    assert order.index("tsumekomi") < order.index("ai-kuse")


def test_snapshot_and_compare(tmp_path, capsys):
    p = tmp_path / "x.md"
    p.write_text("上限は 120 字で、`limits.yaml` に書く。https://example.com を見る。\n", encoding="utf-8")
    assert naoshi.main(["snapshot", str(p)]) == 0
    p.write_text("上限は `limits.yaml` に書く。https://example.com を見る。\n", encoding="utf-8")
    capsys.readouterr()
    assert naoshi.main(["compare", str(p)]) == 1
    out = capsys.readouterr().out
    assert "120" in out and "limits.yaml" not in out


def test_hook_fixes_html_and_reports_warn(files):
    md, html = files
    code, msg = hook.run({"tool_input": {"file_path": str(html)}})
    assert code == 2 and "kumihan" in msg
    assert 'lang="ja"' in html.read_text(encoding="utf-8")
    code, msg = hook.run({"tool_input": {"file_path": str(md)}})
    assert code == 2 and "warn" in msg


def test_hook_is_quiet_for_other_files_and_when_disabled(tmp_path, files, monkeypatch):
    py = tmp_path / "a.py"
    py.write_text("x = 1\n", encoding="utf-8")
    assert hook.run({"tool_input": {"file_path": str(py)}}) == (0, "")
    monkeypatch.setenv("AI_KUSE_HOOK", "0")
    assert hook.run({"tool_input": {"file_path": str(files[0])}}) == (0, "")


def test_hook_main_survives_bad_input(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert hook.main() == 0
