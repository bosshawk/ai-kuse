#!/usr/bin/env bash
# ~/.claude/skills/ai-kuse からこのリポジトリへ symlink を張る
set -euo pipefail
src="$(cd "$(dirname "$0")" && pwd)"
dest="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/ai-kuse"
mkdir -p "$(dirname "$dest")"
if [ -e "$dest" ] && [ ! -L "$dest" ]; then
  echo "既にフォルダがあります（symlink ではない）: $dest" >&2
  echo "中身を確かめてから消し、もう一度実行してください。" >&2
  exit 1
fi
ln -sfn "$src" "$dest"
echo "リンクしました: $dest -> $src"
command -v uv >/dev/null || echo "注意: uv が見つかりません。https://docs.astral.sh/uv/ から入れてください。" >&2
