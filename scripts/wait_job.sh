#!/usr/bin/env bash
# 安全等待：等 PID 退出或等哨兵文件出现，自带超时。
# 用法：
#   ./wait_job.sh --pid 12345 --timeout 900
#   ./wait_job.sh --file .done --timeout 900
# 返回：0 = 完成，1 = 超时（调用方据此触发熔断）
set -u

MODE=""; TARGET=""; TIMEOUT=900
while [ $# -gt 0 ]; do
  case "$1" in
    --pid)     MODE=pid;  TARGET="$2"; shift 2 ;;
    --file)    MODE=file; TARGET="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

[ -z "$MODE" ] && { echo "用法: $0 --pid <PID> | --file <哨兵文件> [--timeout 秒]" >&2; exit 2; }

START=$(date +%s)
while :; do
  if [ "$MODE" = pid ]; then
    kill -0 "$TARGET" 2>/dev/null || { echo "PID $TARGET 已退出"; exit 0; }
  else
    [ -f "$TARGET" ] && { echo "哨兵文件已出现：$TARGET"; exit 0; }
  fi

  NOW=$(date +%s)
  if [ $((NOW - START)) -ge "$TIMEOUT" ]; then
    echo "超时 ${TIMEOUT}s，目标未完成 —— 触发熔断：停止、记录卡点、交付已完成部分" >&2
    exit 1
  fi
  sleep 5
done
