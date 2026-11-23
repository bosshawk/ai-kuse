# ai-kuse

AI が書いた日本語の文章によく出る語（AI の口癖）を見つけて、言い換えを提案する Claude Code のスキルです。語の一覧は YAML で管理します。

<!-- ai-kuse-disable -->
たとえば「設定はこの YAML を正本とする」「詳細は次の節で説明する」のような文の「正本」「節」を見つけ、「基準にする」「セクション」のような候補を、文脈に合わせて出します。
<!-- ai-kuse-enable -->

[yomiyasu](https://github.com/nanaism/yomiyasu) が文章全体を推敲するのに対し、ai-kuse は語の選び方だけを扱います。併用するときは、ai-kuse で語を直してから yomiyasu をかけます。

## しくみ

1. `scripts/check.py` が `terms/*.yaml` のパターンで本文を調べ、当たった箇所を出す。コードブロック、インラインコード、URL は見ない。
2. Claude が当たった箇所の前後を読み、直す・残す・確かめるのどれかに決め、直す箇所には言い換えの案を出す。

検出をスクリプトに任せているので、同じ文章なら毎回同じ箇所が出ます。言い換えるかどうかの判断だけを Claude が行います。方針を決めたときの比較は [設計案](https://claude.ai/artifact/FmbVMetuhF5ALZVPcoCrWx)（非公開）にあります。

## インストール

```bash
./install.sh
```

`~/.claude/skills/ai-kuse` からこのフォルダへ symlink を張ります。必要なのは [uv](https://docs.astral.sh/uv/) だけです（PyYAML は実行時に uv が入れます）。

## 使い方

Claude Code で:

| 呼び出し | すること |
|---|---|
| `/ai-kuse docs/design.md` | 検出して提案する。ファイルは書き換えない |
| `/ai-kuse fix docs/design.md` | 直すと決めた箇所をファイルに反映する |
| `/ai-kuse add 語 言い換え` | 語を一覧に登録する |
| `/ai-kuse list` | 登録済みの語を見る |

CLI だけでも使えます。

```bash
uv run --script scripts/check.py docs/*.md
```

```bash
uv run --script scripts/check.py --format json --severity warn --fail-on warn README.md
```

## 語の一覧の書き方

<!-- ai-kuse-disable -->
```yaml
terms:
  - id: setsu
    term: 節
    category: doc-structure          # categories に書いた分類
    severity: warn                   # warn: 原則直す / info: 文脈しだい
    match:
      regex: ['(この|本|次の|前の)節', '節(では|で|に|を)']
      exclude: [季節, 節約, 調節]      # 当たっても無視する語
      exclude_regex: ['第?[0-9]+\s*節']
    why: 記事や README の区切りを「節」と呼ぶのは section の直訳。
    suggest: [セクション, 章, 以下]
    keep_when: [書籍・論文で章節番号を振っているとき]
    examples:                        # bad は当たり、good は当たらないこと
      - bad: 詳細は次の節で説明する。
        good: 詳細は次のセクションで説明する。
```
<!-- ai-kuse-enable -->

足したら検査します。

```bash
uv run --script scripts/validate.py
```

今の一覧（`terms/tech.yaml`）は技術文書向けの41語です。どの語も、作成者が AI の技術文書でよく見ると判断して選んだもので、出現頻度はまだ測っていません。

## プロジェクトごとの除外

リポジトリの最上位に `.ai-kuse/allow.txt` を置くと、そこに書いた id か語は検出しません。1行だけ外すには行末に `<!-- ai-kuse-ignore -->`、範囲を外すには `<!-- ai-kuse-disable -->` と `<!-- ai-kuse-enable -->` で囲みます。

## テスト

```bash
uv run --with pytest --with pyyaml --with jsonschema pytest -q
```
