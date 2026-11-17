#!/usr/bin/env python3
"""帧核对：截图必须存在、命名必须是分秒、时间必须落在所属段内；
每张帧必须有同名识别原文，卡里的界面文字必须是该文件的逐字子串。
用法：python3 check_frames.py library/series/wb-a
"""
import argparse
import os
import re

from c2c_common import (Report, card_type, field, load_cards, load_source,
                        mmss, norm, parse_range, ui_quotes)

RE_FRAME = re.compile(r'^ep(\d+)-(\d{2,3})(\d{2})\.(?:jpg|jpeg|png)$')
MIN_TEXT = 20   # 识别原文去掉空白后至少这么多字，否则当作没读

ap = argparse.ArgumentParser()
ap.add_argument('series')
a = ap.parse_args()

R = Report()
src = load_source(a.series)
video, alltext = src['video'], src['all']
cards = load_cards(a.series)
n = ok = 0

for c in cards:
    cid = c['id'] or os.path.basename(c['path'])
    typ = card_type(c)
    shot = field(c, '截图')
    if not shot:
        if typ == 'S' and video:
            R.e(f'{cid}：步骤卡没有截图')
        continue
    n += 1
    path = os.path.join(a.series, shot)
    if not os.path.isfile(path):
        R.e(f'{cid}：截图文件不存在 {shot}')
        continue

    if video:
        m = RE_FRAME.match(os.path.basename(shot))
        rg = parse_range(field(c, '所属段'))
        if not m:
            R.e(f'{cid}：截图文件名不是 epNN-MMSS.jpg：{shot}')
        elif int(m[3]) >= 60:
            R.e(f'{cid}：文件名里的秒是 {m[3]}，不小于 60，'
                f'多半是把总秒数当成分秒写了：{shot}')
        elif not rg:
            R.e(f'{cid}：所属段读不出来，无法核对截图时间')
        else:
            ep, t = int(m[1]), int(m[2]) * 60 + int(m[3])
            if ep != rg[0] or not rg[1] <= t <= rg[2]:
                R.e(f'{cid}：截图在第{ep}集 {mmss(t)}，不在所属段'
                    f'（第{rg[0]}集 {mmss(rg[1])}–{mmss(rg[2])}）内')

    # 识别原文：同名 .txt，必须是这次抽帧之后的
    txt = os.path.splitext(path)[0] + '.txt'
    if not os.path.isfile(txt):
        R.e(f'{cid}：缺识别原文 {os.path.basename(txt)}'
            f'（每张帧都要存 understand_images 的返回原文）')
        continue
    if os.path.getmtime(txt) < os.path.getmtime(path):
        R.e(f'{cid}：识别原文比截图旧，重抽帧后没重读')
        continue
    flat = re.sub(r'\s+', '', open(txt, encoding='utf-8').read())
    if len(flat) < MIN_TEXT:
        R.e(f'{cid}：识别原文是空的或太短：{os.path.basename(txt)}')
        continue

    quotes = ui_quotes(c)
    if not quotes:
        msg = f'{cid}：画面识别里没有用「」括起的界面文字，无法核对画面'
        if typ == 'S':
            R.e(msg)
        else:
            R.w(msg)
    bad = [q for q in quotes if re.sub(r'\s+', '', q) not in flat]
    for q in bad:
        R.e(f'{cid}：界面文字「{q}」不在识别原文里（可能读错或改写）')
    if quotes and not bad:
        ok += 1

    for q in ui_quotes(c, ('路径',)):
        if q in quotes or re.sub(r'\s+', '', q) in flat or norm(q) in alltext:
            continue
        R.w(f'{cid}：路径里的「{q}」在这张截图和校正稿里都找不到，请对照原片确认')

print(f'核对 {n} 张截图，其中 {ok} 张的界面文字全部对上')
R.done('帧核对')
