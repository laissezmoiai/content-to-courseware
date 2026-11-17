#!/usr/bin/env python3
"""转写一个系列的全部音频，合并成 sources/raw.md。
用法：python3 asr.py library/series/wb-a --prompt "WorkBuddy、Plan 模式、Ask 模式"
读 sources/media/NN.wav；可选 sources/titles.json，形如 {"1": "认识它"}。
"""
import argparse
import glob
import json
import os
import re
import time
import wave

import numpy as np
from faster_whisper import WhisperModel

ap = argparse.ArgumentParser()
ap.add_argument('series')
ap.add_argument('--prompt', default='')
ap.add_argument('--model', default='small')
a = ap.parse_args()

src = os.path.join(a.series, 'sources')
tp = os.path.join(src, 'titles.json')
titles = json.load(open(tp, encoding='utf-8')) if os.path.isfile(tp) else {}
os.makedirs(os.path.join(src, 'subs'), exist_ok=True)


def load(p):
    with wave.open(p, 'rb') as w:
        data = w.readframes(w.getnframes())
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0


m = WhisperModel(a.model, device='cpu', compute_type='int8', cpu_threads=2)
parts = []
for p in sorted(glob.glob(os.path.join(src, 'media', '*.wav'))):
    n = int(re.search(r'(\d+)\.wav$', p)[1])
    out = os.path.join(src, 'subs', f'{n:02d}.md')
    if not os.path.exists(out):
        t = time.time()
        segs, _ = m.transcribe(load(p), language='zh', beam_size=5, vad_filter=True,
                               condition_on_previous_text=False,
                               hotwords=a.prompt or None)
        lines = [f'[{int(s.start // 60):02d}:{int(s.start % 60):02d}] {s.text.strip()}'
                 for s in segs]
        head = f'# 第{n}集 {titles.get(str(n), "")}'.rstrip()
        open(out, 'w', encoding='utf-8').write(head + '\n\n' + '\n'.join(lines) + '\n')
        print(f'第{n}集完成，{round(time.time() - t, 1)} 秒，{len(lines)} 行', flush=True)
    parts.append(open(out, encoding='utf-8').read().strip())

open(os.path.join(src, 'raw.md'), 'w', encoding='utf-8').write('\n\n'.join(parts) + '\n')
print(f'已写入 {os.path.join(src, "raw.md")}，共 {len(parts)} 集')
