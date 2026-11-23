# AGENTS.md

このリポジトリは、Claude Code のスキル `ai-kuse` の本体です。AI が書いた日本語によく出る語を YAML の一覧で検出し、言い換えを提案します。個人用で、`~/.claude/skills/ai-kuse` からこのフォルダへ symlink を張って使います。

CLAUDE.md は置いていません。Claude Code v2.1.277 以降は、CLAUDE.md がなければこのファイルを直接読みます（[公式ドキュメント](https://code.claude.com/docs/en/memory.md)）。Claude 専用の指示が必要になったら、CLAUDE.md を作って1行目に `@AGENTS.md` を書きます。

## 構成

| パス | 中身 |
|---|---|
| `SKILL.md` | スキルの指示。呼び出し条件と、check / fix / add / list の手順 |
| `terms/<domain>.yaml` | 語の一覧。今は `tech.yaml`（技術文書向け）だけ |
| `schema/terms.schema.json` | 語の一覧の JSON Schema |
| `scripts/ai_kuse_core.py` | 読み込みと検出の共通処理 |
| `scripts/check.py` | 検出の CLI |
| `scripts/validate.py` | 語の一覧の検査（schema、id の重複、正規表現、例文） |
| `tests/` | pytest。`fixtures/should_not_hit.md` は誤検出を防ぐための文 |
| `install.sh` | `~/.claude/skills/ai-kuse` に symlink を張る |
| `research/<年-月>-<題>/` | 語の調査。README に方法・結果・偏りを書き、`results/` には件数だけを置く（記事の本文や会話ログは `data/` に置き、コミットしない） |

## コマンド

```bash
uv run --script scripts/validate.py
```

```bash
uv run --with pytest --with pyyaml --with jsonschema pytest -q
```

```bash
uv run --script scripts/check.py README.md
```

スクリプトは PEP 723 のインライン宣言で依存を持ち、`uv run --script` で動かします。依存は PyYAML と jsonschema だけにし、増やすときは理由をコミットメッセージに書きます。Python は 3.11 以上。

## 語を足す・直すとき

- 1語1件。`examples` は必須で、`bad` はその語に当たり、`good` は当たらない文にする。validate.py がこれを確かめる。
- 1字の語や、ほかの語の一部になる語は、`regex` で前後を絞るか `exclude` / `exclude_regex` で除外する。足したら、ふつうの文で当たらないことを `tests/fixtures/should_not_hit.md` に1行足して確かめる。
- 実際の文書で試し、誤検出が多い語は `severity: info` にするか、パターンを絞る。
- `evidence` には調査の数値（10万字あたりの件数）を書く。出典の数値は、自分で開いて確かめたものだけを `note` に書く。
- 変更のあとは validate.py と pytest の両方を通す。

## 文書を書くとき

- README、SKILL.md、コメントは日本語で書く。
- このリポジトリの文書にも、一覧の語を使わない。語そのものを説明する箇所は `<!-- ai-kuse-disable -->` と `<!-- ai-kuse-enable -->` で囲む。書いたら `uv run --script scripts/check.py README.md SKILL.md AGENTS.md` で確かめる。

## コミット

- Conventional Commits（`feat:` `fix:` `docs:` `test:` `chore:`）。本文は日本語でよい。
- 語の追加は `feat(terms): 〇〇を追加` の形にする。
