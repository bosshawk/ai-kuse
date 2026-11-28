#!/usr/bin/env bash
# 開発用: ~/.claude/skills/<スキル名> から、このリポジトリの skills/<スキル名> へ symlink を張る。
# 使うだけなら、Claude Code のプラグイン（README の「インストール」）のほうが手軽。
set -euo pipefail
# Windows の Git Bash では、これがないと ln -s がリンクではなくコピーを作る（開発者モードが必要）
export MSYS=winsymlinks:nativestrict
repo="$(cd "$(dirname "$0")" && pwd)"
skills_dir="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
mkdir -p "$skills_dir"

for src in "$repo"/skills/*/; do
  src="${src%/}"
  name="$(basename "$src")"
  dest="$skills_dir/$name"
  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    echo "既にフォルダがあります（symlink ではない）: $dest" >&2
    echo "中身を確かめてから消し、もう一度実行してください。" >&2
    exit 1
  fi
  if ! ln -sfn "$src" "$dest" 2>/dev/null; then
    echo "symlink を作れませんでした: $dest" >&2
    echo "Windows なら、設定の「開発者向け」で開発者モードをオンにしてから、もう一度実行してください。" >&2
    echo "使うだけなら、Claude Code のプラグイン（README の「インストール」）で入れられます。" >&2
    exit 1
  fi
  echo "リンクしました: $dest -> $src"
done

# 改名前の名前で張ったリンクが残っていれば外す（ai-kuse → kuchiguse）
old="$skills_dir/ai-kuse"
if [ -L "$old" ]; then
  rm "$old"
  echo "古いリンクを外しました: $old（今は kuchiguse）"
fi

command -v uv >/dev/null || echo "注意: uv が見つかりません。https://docs.astral.sh/uv/ から入れてください。" >&2

cat <<MSG

プラグインと両方入れると同じスキルが2つ並ぶので、どちらか一方にしてください。

hook を使うときは、~/.claude/settings.json に次の2つを足してください（自動では書き換えません）:

  "env": { "AI_KUSE_HOOK": "1" },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command", "command": "uv run --script \"$repo/hooks/post_write.py\"" }
        ]
      }
    ]
  }
MSG
