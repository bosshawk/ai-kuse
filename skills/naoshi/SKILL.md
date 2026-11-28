---
name: naoshi
description: 日本語の文書（Markdown と HTML）を読みやすく書き換えるときに、ほかのスキルをまとめて呼ぶスキル。kumihan（折り返し）・tsumekomi（詰め込み）・kuchiguse（AI の口癖）の検出をまとめて出し、決まった順に書き換え、別のエージェントに読み手として読ませる。利用者が naoshi の名前を出して頼んだとき（「/naoshi」「naoshi にかけて」「naoshi で review して」）、「この文書を読みやすくして」「書いた文書を見直して」とはっきり頼んだときに使う。
license: MIT-0
allowed-tools: Bash(uv run --script ${CLAUDE_SKILL_DIR}/scripts/naoshi.py *) Bash(uv run --script ${CLAUDE_SKILL_DIR}/../kumihan/scripts/kumihan.py *)
---

# naoshi

書いた文書をスクリプトで測り、決まった順に書き換えます。最初に書いたときにルールが守られていなくてもかまいません。ここで測って書き換えます。

ただし、指摘をゼロにすることは目的にしません。見せ方をそろえることも目的にしません。指摘ごとに書き換えるか残すかを決め、残したものは理由を添えて返します。

## 使い方の種類

| 呼び出し | すること | ファイル |
|---|---|---|
| `/naoshi <ファイル…>` | 全スキルの指摘をまとめて出す（check） | 変えない |
| `/naoshi fix <ファイル…>` | 決まった順に書き換え、もう一度測る | 変える |
| `/naoshi review <ファイル…>` | 別のエージェントが読み手として読む | 変えない |
| `/naoshi fix --from-review` | review の指摘のうち、利用者が選んだものだけ書き換える | 変える |
| `/naoshi fix --only <スキル> <ファイル…>` | 1つのスキルの指摘だけ書き換える | 変える |

対象の決め方: 引数のファイル → 依頼に貼られた文章（一時ファイルに書いてから渡す）→ 直前に自分が書いた本文のファイル、の順。どれもなければ尋ねる。

## check

```bash
uv run --script ${CLAUDE_SKILL_DIR}/scripts/naoshi.py check <ファイル…>
```

結果をスキルごとにまとめて返す。各指摘の判断（書き換える・残す・確かめる）はまだしない。件数が多いときは warn を先に、info は件数だけ示す。

## fix

順番は変えない。構造を変えると文も変わるため、大きい変更から小さい変更へ進む。

1. **組版（HTML のみ、全自動）**
   ```bash
   uv run --script ${CLAUDE_SKILL_DIR}/../kumihan/scripts/kumihan.py fix <ファイル…>
   ```
2. **控える**: 書き換える前に、数値・URL・コード・英字の名前を控える。
   ```bash
   uv run --script ${CLAUDE_SKILL_DIR}/scripts/naoshi.py snapshot <ファイル…>
   ```
3. **測る**: `naoshi.py check --format findings <ファイル…>`
4. **詰め込み（tsumekomi）**: 指摘ごとに、書き換える・残す・確かめるを決める。判断の基準は `../tsumekomi/SKILL.md` の「check」に従う。
5. **語（kuchiguse）**: 指摘ごとに、言い換える・残す・確かめるを決める。判断の基準は `../kuchiguse/SKILL.md` の「check」に従う。
6. **測り直す**: もう一度 check を実行する。書き換えると決めた指摘が残っていれば、4 と 5 をもう1回だけ行う。2回で消えなければ、そのまま報告する。
7. **比べる**: 控えた情報が消えていないか確かめる。
   ```bash
   uv run --script ${CLAUDE_SKILL_DIR}/scripts/naoshi.py compare <ファイル…>
   ```
   消えたものがあれば、移した先がないかを確かめ、なければ元に戻す。
8. **返す**: 次の書式でまとめる。
   ```
   ## naoshi の結果（書き換えた X / 残した Y / 確かめたい Z）

   ### 書き換えた所
   | 場所 | スキル | 元 | 後 |
   |---|---|---|---|

   ### 残した所
   | 場所 | スキル | 理由 |
   |---|---|---|

   ### 確かめたい点
   - plan.md:18: 「処理をまとめる」は、どのモジュールにまとめる意図ですか。
   ```

守ること:
- 指摘のない所は変えない。文書全体を書き換えない。
- 原文にない事実、数値、理由を足さない。
- 文書のほかの所や、ほかの文書の見せ方に合わせない。その箇所の中身に合う見せ方にする。

文の推敲が要りそうなら、最後に yomiyasu を使えることを1行で添える（naoshi からは呼ばない）。

## review

書いた本人が見直すと、自分の文を正しいと思い込みます。review は、書いた会話を知らない別のエージェントに任せます。

1. 先に `naoshi.py check` を実行しておく（スクリプトで測れる指摘は review に含めない）。
2. HTML なら、画面写真を2枚撮る（幅 1280px と 390px）。アプリ内ブラウザか Playwright が使えるときだけ。使えなければ写真なしで進め、その旨を報告に書く。
3. Agent ツールで読み手役のエージェントを1つ起動する。渡すのは次の3つだけで、書いたときの会話や意図は渡さない。
   - ファイルのパス
   - `${CLAUDE_SKILL_DIR}/references/review.md` の「読み手役への指示」
   - 画面写真のパス（あれば）
4. 返ってきた指摘を、check の指摘と分けて一覧にする。review の指摘は判断が入るので、すべて提案として扱う。
5. 利用者に、どれを書き換えるかを選んでもらう。選ばれたものだけを `fix --from-review` で書き換える。書き換え方は fix の 4 と同じく、その箇所に合う見せ方を選ぶ。

## hook

`hooks/post_write.py` を Claude Code の PostToolUse hook に入れると、Markdown と HTML を保存するたびに次のことが起きる（設定は README の「hook」）。

- HTML なら、kumihan fix が自動で入る。
- tsumekomi と kuchiguse の warn が上位5件まで返ってくる。返ってきたら、その場で書き換えるか、残す理由を1行で書く。

止めたいときは、環境変数 `AI_KUSE_HOOK=0` を設定する。
