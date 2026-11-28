---
name: kumihan
description: 日本語の HTML（アーティファクト、レポート、説明ページ）の組版を整えるスキル。日本語の本文を含む HTML ファイルを書くとき・書き換えるときに使う。lang="ja" と、文節で折り返す組版CSSを入れ、「表示す／る。」のような語の途中の折り返しを防ぐ。色・フォント・レイアウト・文章の中身は扱わない。Markdown は扱わない。
allowed-tools: Bash(uv run --script ${CLAUDE_SKILL_DIR}/scripts/kumihan.py *)
---

# kumihan

日本語の HTML で、語の途中で折り返す・行頭に小さい仮名が来る、といった組版の乱れを防ぎます。CSS を入れるのはスクリプトで、あなたが CSS を手で書く必要はありません。

## 書くとき

1. 本文を包むいちばん外側の要素（`<html>`、なければ `<body>` か `<main>`）に `lang="ja"` を付ける。アーティファクトのように `<html>` を自分で書かないページでは、`<main lang="ja">` にする。
2. 文の途中で `<br>` を入れて改行しない。折り返しはブラウザに任せる。
3. 書き終えたら fix を実行する。組版CSSはこれで入る。
   ```bash
   uv run --script ${CLAUDE_SKILL_DIR}/scripts/kumihan.py fix <ファイル…>
   ```
   hook を入れていれば、保存のたびに自動で実行される。fix のあとでファイルを編集するときは、先に読み直す。

## 調べるだけのとき

```bash
uv run --script ${CLAUDE_SKILL_DIR}/scripts/kumihan.py check <ファイル…>
```

| id | 意味 | 対処 |
|---|---|---|
| `no-lang` | `lang="ja"` がない | fix で付く |
| `lang-mismatch` | `<html lang="en">` などのまま日本語を書いている | `lang="ja"` に変えるか、日本語の部分を包む要素に付ける |
| `no-base-css` | 組版CSSが入っていない | fix で入る |
| `manual-br` | 文の途中を `<br>` で改行している | `<br>` を消すか、文や項目を分ける |

## 組版CSSの中身

`${CLAUDE_SKILL_DIR}/assets/ja-base.css` にあります。`word-break: auto-phrase`（文節で折り返す）、`line-break: strict`、`text-wrap: pretty` などの、折り返しと禁則の指定だけです。`:where()` で詳細度を 0 にしているので、ページ側の指定があればそちらが勝ちます。

文節の折り返しが効くのは Chrome と Edge（119 以降）です。Safari と Firefox では通常の折り返しになります。
