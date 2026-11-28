# ai-kuse

AI が書いた日本語の文書によく出る癖を見つけて、読みやすく書き換えるためのスキル集です。語の癖（AI の口癖）のほかに、語の途中での折り返しや、表・カード・箇条書きへの詰め込みも扱います。Claude Code のプラグインとして入れるのがおすすめですが、Agent Skills に対応したほかのエージェントでも使えます。

最初に書くときにルールを守らせるのは難しいので、書いたあとにスクリプトで測って書き換える作りにしています。測るのはスクリプトで、書き換えるか残すかは Claude が文脈で決めます。見せ方（表にするか、箇条にするか）はそろえません。

## スキル

| スキル | 扱うこと | いつ使うか |
|---|---|---|
| [naoshi](skills/naoshi/SKILL.md) | ほかのスキルをまとめて呼ぶ。review も行う | 呼び出して使う |
| [tsumekomi](skills/tsumekomi/SKILL.md) | 表のセル・カード・箇条・一文の詰め込み | 書いたあと |
| [kuchiguse](skills/kuchiguse/SKILL.md) | AI の口癖のワード | 書いたあと |
| [kumihan](skills/kumihan/SKILL.md) | 日本語の HTML の折り返し（組版CSS） | HTML を書くとき（自動） |
| [katachi](skills/katachi/SKILL.md) | 読みにくくなる状態の一覧 | 書く前（自動） |

文の推敲は [yomiyasu](https://github.com/nanaism/yomiyasu) に任せます。併用するときは、naoshi で書き換えてから yomiyasu をかけます。

書き換える順番は、変更の大きいものからです。

1. kumihan: `lang="ja"` と組版CSSを入れる（スクリプトだけで済む）
2. tsumekomi: 詰め込みを分ける
3. kuchiguse: ワードを言い換える
4. 測り直し、数値・URL・名前が消えていないか比べる

## インストール

どの方法でも [uv](https://docs.astral.sh/uv/) が要ります（PyYAML は実行時に uv が入れます）。

### Claude Code（おすすめ）

```
/plugin install ai-kuse --marketplace bosshawk/ai-kuse
```

Claude Code 2.1.275 より前なら、2行に分けます。

```
/plugin marketplace add bosshawk/ai-kuse
/plugin install ai-kuse@ai-kuse
```

プラグインとして入れると、5つのスキルがまとめて入り、hook も使えます。スキルは `/ai-kuse:naoshi` のように、プラグイン名を付けて呼びます。更新は `/plugin update ai-kuse@ai-kuse` です。

### ほかのエージェント（Codex、Cursor、Copilot など）

```bash
npx skills add bosshawk/ai-kuse --skill '*'
```

```bash
gh skill install bosshawk/ai-kuse --all --scope user
```

naoshi はほかのスキルを読むので、5つまとめて入れてください。この方法では hook は入りません。SKILL.md の手順は Claude Code を前提に書いているため、ほかのエージェントではスクリプトのパスを読み替える必要があることがあります。

### 開発する人

```bash
./install.sh
```

`~/.claude/skills/<スキル名>` から、このリポジトリの `skills/<スキル名>` へ symlink を張ります。書き換えがすぐに反映されます。プラグインと両方入れると同じスキルが2つ並ぶので、どちらか一方にしてください。Windows の Git Bash では、symlink を作るのに開発者モードが要ります。

## 使い方

Claude Code で（プラグインなら `/ai-kuse:naoshi` のように呼びます）:

| 呼び出し | すること |
|---|---|
| `/naoshi docs/plan.md` | 全スキルの指摘をまとめて見る。ファイルは書き換えない |
| `/naoshi fix docs/plan.md` | 決まった順に書き換え、測り直す |
| `/naoshi review docs/plan.md` | 書いた会話を知らない別のエージェントが、読み手として読む |
| `/tsumekomi docs/plan.md` | 詰め込みだけを見る |
| `/kuchiguse docs/plan.md` | ワードだけを見る |

CLI だけでも使えます。

```bash
uv run --script skills/naoshi/scripts/naoshi.py check docs/plan.md page.html
```

```bash
uv run --script skills/kumihan/scripts/kumihan.py fix page.html
```

## hook

Markdown と HTML を保存するたびに測る hook があります。入れた人全員に勝手に効かないよう、初めは止まっています。使うときは `~/.claude/settings.json` に次を足します。

```json
{
  "env": { "AI_KUSE_HOOK": "1" }
}
```

- HTML なら、kumihan fix が自動で入ります。
- tsumekomi と kuchiguse の warn を上位5件まで Claude に返します。info や review は返しません。

プラグインなら hook の登録は済んでいるので、上の設定だけで動きます。install.sh で入れた場合は、hook の登録も要ります（install.sh を実行すると設定例が表示されます）。

## 全スキル共通の指摘

各スキルの検出スクリプトは、`--format findings` で同じ JSON を出します（[shared/finding.schema.json](shared/finding.schema.json)）。naoshi はこれを並べるだけです。スキルどうしの内部の書式なので、文書の見た目には関係しません。

## kuchiguse: AI の口癖のワード

<!-- ai-kuse-disable -->
たとえば「設定はこの YAML を正本とする」「詳細は次の節で説明する」のような文の「正本」「節」を見つけ、「基準にする」「セクション」のような候補を、文脈に合わせて出します。
<!-- ai-kuse-enable -->

| 呼び出し | すること |
|---|---|
| `/kuchiguse docs/design.md` | 検出して提案する。ファイルは書き換えない |
| `/kuchiguse fix docs/design.md` | 言い換えると決めた箇所をファイルに反映する |
| `/kuchiguse add ワード 言い換え` | ワードを一覧に登録する |
| `/kuchiguse list` | 登録済みのワードを見る |

```bash
uv run --script skills/kuchiguse/scripts/check.py --format json --severity warn --fail-on warn README.md
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
uv run --script skills/kuchiguse/scripts/validate.py
```

今の一覧（`skills/kuchiguse/terms/tech.yaml`）は技術文書向けで、ワードは109件です。出現頻度の調査（[research/2026-11-term-survey](skills/kuchiguse/research/2026-11-term-survey/README.md)）の結果を、各ワードの `evidence` に書いています。

### 自分のワードを足す

プラグインや npx skills で入れたスキルのフォルダは、更新で置き換わります。`/kuchiguse add` で足したワードは、その外の次の場所に書かれ、同梱の一覧と一緒に読まれます。

| 場所 | 効く範囲 |
|---|---|
| `<リポジトリの最上位>/.ai-kuse/terms/*.yaml` | そのプロジェクトだけ |
| `~/.ai-kuse/terms/*.yaml` | すべてのプロジェクト（`AI_KUSE_HOME` で変えられる） |

書き方は同梱の一覧と同じです。よく使われるワードなら、このリポジトリへの提案も歓迎します。

### ワードを足す前の調査

`/kuchiguse survey <ワード>` で、AI の文章と人の文章での使い方と件数を比べてから足すかを決めます。手順と判断の基準は [references/survey.md](skills/kuchiguse/references/survey.md) にあります。

```bash
uv run --script skills/kuchiguse/scripts/survey.py prepare
```

```bash
uv run --script skills/kuchiguse/scripts/survey.py neighbors 層
```

文章群（会話ログと Qiita の記事）は `~/.cache/ai-kuse` に置き、リポジトリには入れません。

## tsumekomi: 詰め込みの目安

目安は [skills/tsumekomi/limits.yaml](skills/tsumekomi/limits.yaml) にあります。数値は仮で、読みやすいと感じた文書を測って調整します。調べるための文書（API の一覧など）は、`<!-- tsumekomi: profile=reference -->` を書くと表のセルの目安がゆるみます。

## プロジェクトごとの除外

| スキル | 1行だけ外す | 範囲を外す |
|---|---|---|
| kuchiguse | 行末に `<!-- ai-kuse-ignore -->` | `<!-- ai-kuse-disable -->` 〜 `<!-- ai-kuse-enable -->` |
| tsumekomi | 行末に `<!-- tsumekomi-ignore -->` | `<!-- tsumekomi-disable -->` 〜 `<!-- tsumekomi-enable -->` |

kuchiguse は、リポジトリの最上位に `.ai-kuse/allow.txt` を置くと、そこに書いた id かワードを検出しません。

## テスト

```bash
uv run --with pytest --with pyyaml --with jsonschema pytest -q
```

```bash
claude plugin validate .
```

## ライセンス

[MIT No Attribution（MIT-0）](LICENSE)。著作権の表示を残す必要もなく、自由に使い、書き換え、配れます。
