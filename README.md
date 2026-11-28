# ai-kuse

AI が書いた日本語の文書によく出る癖を見つけて、読みやすく書き換えるための Claude Code のスキル集です。語の癖（AI の口癖）のほかに、語の途中での折り返しや、表・カード・箇条書きへの詰め込みも扱います。

最初に書くときにルールを守らせるのは難しいので、書いたあとにスクリプトで測って書き換える作りにしています。測るのはスクリプトで、書き換えるか残すかは Claude が文脈で決めます。見せ方（表にするか、箇条にするか）はそろえません。

## スキル

| スキル | 扱うこと | いつ使うか |
|---|---|---|
| [naoshi](skills/naoshi/SKILL.md) | ほかのスキルをまとめて呼ぶ。review も行う | `/naoshi` で呼ぶ |
| [tsumekomi](skills/tsumekomi/SKILL.md) | 表のセル・カード・箇条・一文の詰め込み | 書いたあと |
| [ai-kuse](skills/ai-kuse/SKILL.md) | AI の口癖のワード | 書いたあと |
| [kumihan](skills/kumihan/SKILL.md) | 日本語の HTML の折り返し（組版CSS） | HTML を書くとき（自動） |
| [katachi](skills/katachi/SKILL.md) | 読みにくくなる状態の一覧 | 書く前（自動） |

文の推敲は [yomiyasu](https://github.com/nanaism/yomiyasu) に任せます。併用するときは、naoshi で書き換えてから yomiyasu をかけます。

書き換える順番は、変更の大きいものからです。

1. kumihan: `lang="ja"` と組版CSSを入れる（スクリプトだけで済む）
2. tsumekomi: 詰め込みを分ける
3. ai-kuse: ワードを言い換える
4. 測り直し、数値・URL・名前が消えていないか比べる

## インストール

```bash
./install.sh
```

`~/.claude/skills/<スキル名>` から、このリポジトリの `skills/<スキル名>` へ symlink を張ります。必要なのは [uv](https://docs.astral.sh/uv/) だけです（PyYAML は実行時に uv が入れます）。

Windows の Git Bash では、symlink を作るのに開発者モードが要ります。

## 使い方

Claude Code で:

| 呼び出し | すること |
|---|---|
| `/naoshi docs/plan.md` | 全スキルの指摘をまとめて見る。ファイルは書き換えない |
| `/naoshi fix docs/plan.md` | 決まった順に書き換え、測り直す |
| `/naoshi review docs/plan.md` | 書いた会話を知らない別のエージェントが、読み手として読む |
| `/tsumekomi docs/plan.md` | 詰め込みだけを見る |
| `/ai-kuse docs/plan.md` | ワードだけを見る |

CLI だけでも使えます。

```bash
uv run --script skills/naoshi/scripts/naoshi.py check docs/plan.md page.html
```

```bash
uv run --script skills/kumihan/scripts/kumihan.py fix page.html
```

## hook

`~/.claude/settings.json` に次を足すと、Markdown と HTML を保存するたびに測ります（install.sh を実行すると、このリポジトリのパスを入れた設定が表示されます）。

```json
"hooks": {
  "PostToolUse": [
    {
      "matcher": "Write|Edit|MultiEdit",
      "hooks": [
        { "type": "command", "command": "uv run --script \"/path/to/ai-kuse/hooks/post_write.py\"" }
      ]
    }
  ]
}
```

- HTML なら、kumihan fix が自動で入ります。
- tsumekomi と ai-kuse の warn を上位5件まで Claude に返します。info や review は返しません。
- 環境変数 `AI_KUSE_HOOK=0` で止まります。

## 全スキル共通の指摘

各スキルの検出スクリプトは、`--format findings` で同じ JSON を出します（[shared/finding.schema.json](shared/finding.schema.json)）。naoshi はこれを並べるだけです。スキルどうしの内部の書式なので、文書の見た目には関係しません。

## ai-kuse: AI の口癖のワード

<!-- ai-kuse-disable -->
たとえば「設定はこの YAML を正本とする」「詳細は次の節で説明する」のような文の「正本」「節」を見つけ、「基準にする」「セクション」のような候補を、文脈に合わせて出します。
<!-- ai-kuse-enable -->

| 呼び出し | すること |
|---|---|
| `/ai-kuse docs/design.md` | 検出して提案する。ファイルは書き換えない |
| `/ai-kuse fix docs/design.md` | 言い換えると決めた箇所をファイルに反映する |
| `/ai-kuse add ワード 言い換え` | ワードを一覧に登録する |
| `/ai-kuse list` | 登録済みのワードを見る |

```bash
uv run --script skills/ai-kuse/scripts/check.py --format json --severity warn --fail-on warn README.md
```

方針を決めたときの比較は [設計案](https://claude.ai/artifact/FmbVMetuhF5ALZVPcoCrWx)（非公開）にあります。

### ワードの一覧の書き方

<!-- ai-kuse-disable -->
```yaml
terms:
  - id: setsu
    term: 節
    category: doc-structure          # categories に書いた分類
    severity: warn                   # warn: 原則言い換える / info: 文脈しだい
    match:
      regex: ['(この|本|次の|前の)節', '節(では|で|に|を)']
      exclude: [季節, 節約, 調節]      # 当たっても無視するワード
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
uv run --script skills/ai-kuse/scripts/validate.py
```

今の一覧（`skills/ai-kuse/terms/tech.yaml`）は技術文書向けで、ワードは109件です。出現頻度の調査（[research/2026-11-term-survey](skills/ai-kuse/research/2026-11-term-survey/README.md)）の結果を、各ワードの `evidence` に書いています。

### ワードを足す前の調査

`/ai-kuse survey <ワード>` で、AI の文章と人の文章での使い方と件数を比べてから足すかを決めます。手順と判断の基準は [references/survey.md](skills/ai-kuse/references/survey.md) にあります。

```bash
uv run --script skills/ai-kuse/scripts/survey.py prepare
```

```bash
uv run --script skills/ai-kuse/scripts/survey.py neighbors 層
```

文章群（会話ログと Qiita の記事）は `~/.cache/ai-kuse` に置き、リポジトリには入れません。

## tsumekomi: 詰め込みの目安

目安は [skills/tsumekomi/limits.yaml](skills/tsumekomi/limits.yaml) にあります。数値は仮で、読みやすいと感じた文書を測って調整します。調べるための文書（API の一覧など）は、`<!-- tsumekomi: profile=reference -->` を書くと表のセルの目安がゆるみます。

## プロジェクトごとの除外

| スキル | 1行だけ外す | 範囲を外す |
|---|---|---|
| ai-kuse | 行末に `<!-- ai-kuse-ignore -->` | `<!-- ai-kuse-disable -->` 〜 `<!-- ai-kuse-enable -->` |
| tsumekomi | 行末に `<!-- tsumekomi-ignore -->` | `<!-- tsumekomi-disable -->` 〜 `<!-- tsumekomi-enable -->` |

ai-kuse は、リポジトリの最上位に `.ai-kuse/allow.txt` を置くと、そこに書いた id かワードを検出しません。

## テスト

```bash
uv run --with pytest --with pyyaml --with jsonschema pytest -q
```
