#!/usr/bin/env bash
# 单向同步：仓库 → 技能库，同步后强制 diff 比对。
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DST=~/.opencode/skills/content-to-courseware
rsync -a --delete --exclude '*.pyc' --exclude '__pycache__' "$SRC/" "$DST/"
diff -r "$SRC" "$DST" -x '*.pyc' -x '__pycache__' && echo "同步成功：diff 为空" || { echo "同步不一致！" >&2; exit 1; }
