#!/usr/bin/env bash
# ~/.claude/skills/<スキル名> から、このリポジトリの skills/<スキル名> へ symlink を張る
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
  ln -sfn "$src" "$dest"
  echo "リンクしました: $dest -> $src"
done

command -v uv >/dev/null || echo "注意: uv が見つかりません。https://docs.astral.sh/uv/ から入れてください。" >&2

cat <<EOF

hook を使うときは、~/.claude/settings.json の "hooks" に次を足してください（自動では書き換えません）:

  "PostToolUse": [
    {
      "matcher": "Write|Edit|MultiEdit",
      "hooks": [
        { "type": "command", "command": "uv run --script \"$repo/hooks/post_write.py\"" }
      ]
    }
  ]
EOF
