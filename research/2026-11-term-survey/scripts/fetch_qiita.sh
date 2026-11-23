#!/usr/bin/env bash
# Qiita API v2 から記事を取得する（未認証は 1 時間に 60 回まで）。data/qiita/ に保存する。
set -euo pipefail
cd "$(dirname "$0")/../data" 2>/dev/null || { mkdir -p "$(dirname "$0")/../data"; cd "$(dirname "$0")/../data"; }
mkdir -p qiita
fetch(){ curl -s -A "term-survey-script" "https://qiita.com/api/v2/items?page=$2&per_page=100&query=$3" -o "qiita/$1_$(printf %02d "$2").json"; sleep 1; }
Q1='created%3A%3E%3D2019-01-01+created%3A%3C2022-01-01+stocks%3A%3E%3D20'   # 人の文章（ChatGPT 公開前）
Q2='created%3A%3E%3D2026-01-01+stocks%3A%3E%3D20'                            # 2026 年の記事
for i in $(seq 1 15); do fetch h "$i" "$Q1"; done
for i in $(seq 1 10); do fetch n "$i" "$Q2"; done
