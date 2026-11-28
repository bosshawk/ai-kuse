# AGENTS.md

このリポジトリは、AI が書いた日本語の文書の癖を見つけて書き換えるスキル集です。スキルは `skills/<スキル名>/` に1つずつあります。

同じリポジトリを3通りで配ります。どれでも動くように保ちます。

- Claude Code のプラグイン（リポジトリの最上位がプラグイン兼マーケットプレイス。プラグイン名は `ai-kuse`）
- Agent Skills（`npx skills add`、`gh skill install` が `skills/*/SKILL.md` を読む）
- 開発用の symlink（`install.sh`）

ほかの人が使う前提なので、スキルのフォルダに利用者のデータを書かない（プラグインでは更新で消える）。利用者が足すワードは `~/.ai-kuse/terms/` か、プロジェクトの `.ai-kuse/terms/` に置く。

測るのはスクリプト、書き換えるか残すかを決めるのは Claude、という分け方をすべてのスキルで守ります。ルールには「読みにくい状態」だけを書き、見せ方（表・箇条・カード）を決めるルールは足しません。

CLAUDE.md は置いていません。Claude Code v2.1.277 以降は、CLAUDE.md がなければこのファイルを直接読みます（[公式ドキュメント](https://code.claude.com/docs/en/memory.md)）。Claude 専用の指示が必要になったら、CLAUDE.md を作って1行目に `@AGENTS.md` を書きます。

## 構成

| パス | 中身 |
|---|---|
| `skills/naoshi/` | ほかのスキルをまとめて呼ぶ。review も行う |
| `skills/tsumekomi/` | 詰め込みを測る。目安は `limits.yaml` |
| `skills/kumihan/` | 日本語の HTML の組版CSS |
| `skills/katachi/` | 読みにくくなる状態の一覧 |
| `skills/kuchiguse/` | AI の口癖のワード。下の表 |
| `.claude-plugin/` | `plugin.json`（版とライセンス）と `marketplace.json` |
| `hooks/hooks.json` | プラグインの hook の登録 |
| `hooks/post_write.py` | hook の本体。`AI_KUSE_HOOK=1` のときだけ動く |
| `shared/finding.schema.json` | 全スキル共通の指摘の書式 |
| `tests/` | スキルをまたいだテスト |
| `install.sh` | 開発用。`skills/*` を symlink する |
| `LICENSE` | MIT-0 |

kuchiguse は、もとは ai-kuse という名前でした。プラグイン名と同じだと `/ai-kuse:ai-kuse` になるため改名しました。本文の印（`ai-kuse-ignore` など）と `.ai-kuse/` は、使っている文書があるので名前を変えていません。

`skills/kuchiguse/` の中身:

| パス | 中身 |
|---|---|
| `SKILL.md` | スキルの指示。呼び出し条件と、check / fix / add / list の手順 |
| `terms/<domain>.yaml` | ワードの一覧。今は `tech.yaml`（技術文書向け）だけ |
| `schema/terms.schema.json` | ワードの一覧の JSON Schema |
| `scripts/ai_kuse_core.py` | 読み込みと検出の共通処理 |
| `scripts/check.py` | 検出の CLI |
| `scripts/survey.py` | ワードを足す前の調査（文章群の準備、件数の比較、直前の言葉ごとの集計、用例、evidence の更新） |
| `references/survey.md` | ワードを足すときの調査の手順と判断の基準 |
| `scripts/validate.py` | ワードの一覧の検査（schema、id の重複、正規表現、例文） |
| `tests/` | pytest。`fixtures/should_not_hit.md` は誤検出を防ぐための文 |
| `research/<年-月>-<題>/` | ワードの調査。README に方法・結果・偏りを書き、`results/` には件数だけを置く（記事の本文や会話ログは `data/` に置き、コミットしない） |

各スキルは単独でも動くようにする（symlink 先のフォルダしか見えないため）。naoshi と hook だけが、`skills/` の下のほかのスキルを読む。

## コマンド

```bash
uv run --script skills/kuchiguse/scripts/validate.py
```

```bash
uv run --with pytest --with pyyaml --with jsonschema pytest -q
```

```bash
uv run --script skills/naoshi/scripts/naoshi.py check README.md AGENTS.md skills/*/SKILL.md
```

スクリプトは PEP 723 のインライン宣言で依存を持ち、`uv run --script` で動かします。依存は PyYAML と jsonschema だけにし、増やすときは理由をコミットメッセージに書きます。Python は 3.11 以上。

## ワードを足す・変えるとき

パスは `skills/kuchiguse/` からの相対で書く。

- 手順と判断の基準は `references/survey.md` に従う。足す前に `scripts/survey.py` で使い方と件数を確かめる。
- 文書では、一覧に載せるものを「ワード」と呼ぶ。

- 1ワード1件。`examples` は必須で、`bad` はそのワードに当たり、`good` は当たらない文にする。validate.py がこれを確かめる。
- 1字のワードや、ほかのワードの一部になるワードは、`regex` で前後を絞るか `exclude` / `exclude_regex` で除外する。足したら、ふつうの文で当たらないことを `tests/fixtures/should_not_hit.md` に1行足して確かめる。
- 実際の文書で試し、誤検出が多いワードは `severity: info` にするか、パターンを絞る。
- `evidence` には調査の数値（10万字あたりの件数）を書く。出典の数値は、自分で開いて確かめたものだけを `note` に書く。
- 変更のあとは validate.py と pytest の両方を通す。

## 文書を書くとき

- README、SKILL.md、コメントは日本語で書く。
- このリポジトリの文書にも、一覧のワードを使わない。
- ワードそのものを説明する箇所は `<!-- ai-kuse-disable -->` と `<!-- ai-kuse-enable -->` で囲む。
- 書いたら naoshi で確かめる。
  ```bash
  uv run --script skills/naoshi/scripts/naoshi.py check README.md AGENTS.md skills/*/SKILL.md
  ```

## 目安やルールを足す・変えるとき

- tsumekomi の目安（`limits.yaml`）は、読みやすいと感じた実際の文書を測ってから変える。数値の根拠をコミットメッセージに書く。
- katachi には「読みにくい状態」だけを書く。「比較は表にする」のように見せ方を決める書き方はしない。
- 新しいスキルの検出スクリプトは `--format findings` で `shared/finding.schema.json` の書式を出し、`skills/naoshi/scripts/naoshi.py` の `Checkers` に足す。

## コミット

- Conventional Commits（`feat:` `fix:` `docs:` `test:` `chore:`）。本文は日本語でよい。
- ワードの追加は `feat(terms): 〇〇を追加` の形にする。

## リリース

利用者には、プラグインの版とタグで更新が届く。

1. `.claude-plugin/plugin.json` の `version` を上げる（同じ版のままだと、プラグインの利用者に更新が届かない）。
2. テストと `claude plugin validate .` を通す。
3. main に入れて push してから、`gh skill publish --tag v<版>` でリリースを作る。

タグは gh が作るので、先に打たない。打ってあると「tag already exists」で止まる。
