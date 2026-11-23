#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6", "jsonschema>=4.20"]
# ///
"""terms/*.yaml を検査する。

- JSON Schema（schema/terms.schema.json）に合うか
- id が全ファイルで重ならないか、category が categories にあるか
- 正規表現がコンパイルできるか
- examples の bad がそのワードに当たり、good が当たらないか

使い方: uv run --script scripts/validate.py [terms/tech.yaml ...]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_kuse_core import SCHEMA_PATH, compile_term, find_in_line, load_raw, terms_files  # noqa: E402


def validate(paths: list[Path]) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    seen: dict[str, Path] = {}

    for path in paths:
        name = path.name
        try:
            data = load_raw(path)
        except Exception as e:  # YAML の書式の誤り
            errors.append(f"{name}: YAML を読めません: {e}")
            continue

        schema_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        for e in schema_errors:
            loc = "/".join(str(p) for p in e.path) or "(root)"
            errors.append(f"{name}: {loc}: {e.message}")
        if schema_errors:
            continue

        if data["domain"] != path.stem:
            errors.append(f"{name}: domain '{data['domain']}' がファイル名と違います")
        cats = data["categories"]
        for raw in data["terms"]:
            tid = raw["id"]
            where = f"{name}: {tid}"
            if tid in seen:
                errors.append(f"{where}: id が {seen[tid].name} と重なっています")
            seen[tid] = path
            if raw["category"] not in cats:
                errors.append(f"{where}: category '{raw['category']}' が categories にありません")
            m = raw["match"]
            bad_re = False
            for key in ("regex", "exclude_regex"):
                for s in m.get(key, []):
                    try:
                        re.compile(s)
                    except re.error as e:
                        errors.append(f"{where}: {key} をコンパイルできません: {s} ({e})")
                        bad_re = True
            if bad_re:
                continue
            for lit in m.get("literal", []):
                if lit in m.get("exclude", []):
                    errors.append(f"{where}: '{lit}' が literal と exclude の両方にあります")
            term = compile_term(raw, data["domain"], cats)
            for i, ex in enumerate(raw["examples"], start=1):
                if not find_in_line(ex["bad"], term):
                    errors.append(f"{where}: examples[{i}].bad が当たりません: {ex['bad']}")
                if find_in_line(ex["good"], term):
                    errors.append(f"{where}: examples[{i}].good に当たってしまいます: {ex['good']}")
    return errors


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] if argv else terms_files()
    errors = validate(paths)
    if errors:
        print("\n".join(errors))
        print(f"\nエラー {len(errors)} 件", file=sys.stderr)
        return 1
    total = sum(len(load_raw(p)["terms"]) for p in paths)
    print(f"OK: {len(paths)} ファイル、{total} 件のワード")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
