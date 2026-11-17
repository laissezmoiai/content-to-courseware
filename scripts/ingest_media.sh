#!/usr/bin/env bash
# 取材脚本：视频 → 带定位信息的文本 + 关键帧
# 用法：./ingest_media.sh <url或本地文件> <工作目录>
set -euo pipefail

SRC="$1"
WORK="${2:-./sources}"
mkdir -p "$WORK" "$WORK/frames"

echo "[1/4] 抓字幕（仅在线视频）"
if [[ "$SRC" == http* ]]; then
  yt-dlp --write-subs --write-auto-subs --skip-download \
         --sub-langs "zh-Hans,zh-Hant,zh,en" --sub-format vtt \
         -o "$WORK/video" "$SRC" || echo "  无字幕，转下一步"
  if ls "$WORK"/*.vtt >/dev/null 2>&1; then
    python3 - "$WORK" <<'PY'
import sys, glob, re, os
work = sys.argv[1]
vtt = glob.glob(os.path.join(work, "*.vtt"))[0]
lines, out, last = open(vtt, encoding="utf-8").read().splitlines(), [], ""
for ln in lines:
    m = re.match(r"(\d\d):(\d\d):(\d\d)\.\d+ -->", ln)
    if m:
        last = f"[{m.group(1)}:{m.group(2)}:{m.group(3)}]"
        continue
    if ln.strip() and "-->" not in ln and not ln.startswith(("WEBVTT", "Kind:", "Language:")):
        if out and out[-1].startswith(last):
            out[-1] += " " + ln.strip()
        else:
            out.append(f"{last} {ln.strip()}")
open(os.path.join(work, "raw.md"), "w", encoding="utf-8").write("\n\n".join(out))
print(f"  已写入 {len(out)} 条带时间戳段落")
PY
  fi
fi

echo "[2/4] 抽音频（供转写）"
if [[ "$SRC" == http* ]]; then
  yt-dlp -x --audio-format wav -o "$WORK/audio.%(ext)s" "$SRC"
else
  ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vn -ac 1 -ar 16000 "$WORK/audio.wav"
fi

echo "[3/4] 抽关键帧（每 30 秒一帧）"
ffmpeg -hide_banner -loglevel error -y -i "$SRC" -vf "fps=1/30,scale=1280:-1" \
       "$WORK/frames/%06d.jpg" 2>/dev/null || \
ffmpeg -hide_banner -loglevel error -y -i "$WORK/audio.wav" -f lavfi -i color=c=black:s=16x16 \
       -t 1 "$WORK/frames/000001.jpg" || echo "  抽帧失败（无视频流）"

echo "[4/4] 完成"
echo "  文本：$WORK/raw.md（若字幕缺失，请用 faster-whisper 转写 audio.wav 后自行补时间戳）"
echo "  帧：  $WORK/frames/"
echo "  下一步：人工/模型通读 raw.md，按 SKILL.md 阶段 1 做结构解剖"
