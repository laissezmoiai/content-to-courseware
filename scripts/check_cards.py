#!/usr/bin/env python3
"""采集验收：检查一个系列的全部卡片。
用法：python3 check_cards.py library/series/wb-a --topic-map library/topic-map.md --prefix A --write-index
"""
import argparse
import glob
import json
import os
import re

from c2c_common import (KIND, RE_ID, Report, card_type, field, find_all,
                        in_doc_range, key_at, load_cards, load_source,
                        load_topics, parse_doc_range, parse_point, parse_range,
                        quote_pieces, time_at, unbacked_numbers)

MAX_SPAN = {'S': 240}   # 所属段时长上限（秒），超过只警告
MAX_SPAN_OTHER = 150
CONFIRM_KEYS = ('模式', '素材', '系列代号', '类型')   # 开工确认单必填的字段
RE_BLANK = re.compile(r'[<＜][^>＞]*[>＞]|^[… .]*$')   # 没填或还是占位


def find_runlog(series):
    hits = sorted(glob.glob(os.path.join(series, 'runlog-*.md')))
    if hits:
        return hits[-1]
    plain = os.path.join(series, 'runlog.md')
    return plain if os.path.isfile(plain) else None


def confirm_sheet(path):
    """取 runlog 开头的确认单：第一张表或下一个标题之前的「字段：值」行。"""
    out, started = [], False
    for line in open(path, encoding='utf-8'):
        t = line.strip()
        if not t:
            continue
        if t.startswith('#'):
            if started:
                break
            continue
        if t.startswith('|'):
            break
        started = True
        m = re.match(r'[>\-*\s]*([^：:]{1,20}?)[*\s]*[：:]\s*(.*)', t)
        if m:
            out.append((m[1].strip(), m[2].strip('* ')))
    return out


ap = argparse.ArgumentParser()
ap.add_argument('series')
ap.add_argument('--topic-map', required=True)
ap.add_argument('--prefix')
ap.add_argument('--write-index', action='store_true')
a = ap.parse_args()

R = Report()
topics = load_topics(a.topic_map)
src = load_source(a.series)
video, eps, doc, alltext = src['video'], src['eps'], src['doc'], src['all']
if video and max(e['end'] for e in eps.values()) >= 3 * 3600:
    R.w('有时间戳超过 3 小时，检查是否还是旧格式 [集:分:秒]')

rl = find_runlog(a.series)
if not rl:
    R.e('系列目录没有 runlog-<日期>.md，开工确认单没落盘')
else:
    name = os.path.basename(rl)
    got = {}
    for k, v in confirm_sheet(rl):
        for want in CONFIRM_KEYS:
            if k.startswith(want):
                got.setdefault(want, (k, v))
        if '前缀' in k and not k.startswith('系列代号'):
            got.setdefault('前缀', (k, v))
    miss = [w for w in CONFIRM_KEYS if w not in got]
    if miss:
        R.e(f'{name} 开头不是开工确认单（缺「{"」「".join(miss)}」）；'
            f'确认单要写在阶段记录表之前')
    for k, v in got.values():
        if RE_BLANK.search(v):
            R.e(f'{name}：确认单的「{k}」没填或还是占位：{v or "空"}')
    k, v = got.get('系列代号', ('', ''))
    if v and not RE_BLANK.search(v):
        parts = [x.strip() for x in re.split(r'[/／]', v)]
        folder = os.path.basename(os.path.normpath(a.series))
        if parts[0] != folder:
            R.e(f'{name}：确认单的系列代号是 {parts[0]}，目录是 {folder}')
        pre = parts[1] if '前缀' in k and len(parts) > 1 else got.get('前缀', ('', ''))[1]
        if a.prefix and pre and pre != a.prefix:
            R.e(f'{name}：确认单的前缀是 {pre}，验收命令给的是 {a.prefix}')
        elif a.prefix and not pre:
            R.w(f'{name}：确认单里没写卡号前缀')

cards = load_cards(a.series)
if not cards:
    R.e('cards/ 里没有卡片')
seen, ranges, index = set(), {}, []

for c in cards:
    cid = c['id'] or os.path.basename(c['path'])
    typ = card_type(c)

    if not RE_ID.match(c['id']):
        R.e(f'{cid}：编号格式不对')
    elif c['id'].startswith('M-'):
        R.e(f'{cid}：系列目录里不应该有合成卡')
    else:
        if a.prefix and c['id'].split('-')[0] != a.prefix:
            R.e(f'{cid}：前缀应为 {a.prefix}')
        if c['kind'] in KIND and KIND[c['kind']] != typ:
            R.w(f'{cid}：标题写的是「{c["kind"]}」，编号里的类型是 {typ}')
    if c['id'] in seen:
        R.e(f'{cid}：编号重复')
    seen.add(c['id'])
    if os.path.basename(c['path']) != c['id'] + '.md':
        R.w(f'{cid}：文件名与编号不一致')

    if field(c, '主题') not in topics:
        R.e(f'{cid}：主题「{field(c, "主题")}」不在主题树里')
    if field(c, '状态') not in ('正文级', '附录级'):
        R.e(f'{cid}：状态应为 正文级 或 附录级')
    review = field(c, '回查')
    if not review:
        R.e(f'{cid}：缺回查记录')
    elif re.search(r'无据\s*[1-9]', review):
        R.e(f'{cid}：回查里还有无据的句子')

    pt = rg = dpt = drg = None
    if video:
        pt = parse_point(field(c, '定位点'))
        rg = parse_range(field(c, '所属段'))
        if not pt:
            R.e(f'{cid}：定位点格式应为「第N集 mm:ss」')
        if not rg:
            R.e(f'{cid}：所属段格式应为「第N集 mm:ss–mm:ss」')
        if pt and rg and not (pt[0] == rg[0] and rg[1] <= pt[1] <= rg[2]):
            R.e(f'{cid}：定位点不在所属段内')
        if rg:
            ranges.setdefault(rg, []).append(cid)
            limit = MAX_SPAN.get(typ, MAX_SPAN_OTHER)
            if rg[2] - rg[1] > limit:
                R.w(f'{cid}：所属段长 {rg[2] - rg[1]} 秒，超过 {limit} 秒，检查是否该拆卡')
    else:
        dpt = parse_doc_range(field(c, '定位点'))
        drg = parse_doc_range(field(c, '所属段')) or dpt
        if not dpt:
            R.e(f'{cid}：定位点格式应为「p.47」「第5页」或「第3章 §2」')
        if dpt and drg and not (dpt[0] == drg[0] and drg[1] <= dpt[1] and dpt[2] <= drg[2]):
            R.e(f'{cid}：定位点不在所属段内')

    pieces = quote_pieces(c)
    if not c['f'].get('原文摘录'):
        R.e(f'{cid}：缺原文摘录')
    elif not pieces:
        R.e(f'{cid}：原文摘录太短，每段至少 6 个字')
    for n, (p, shown) in enumerate(pieces):
        if p not in alltext:
            R.e(f'{cid}：摘录不是校正稿原文：{shown[:20]}')
            continue
        if video:
            if not pt:
                continue
            ep = eps.get(pt[0])
            hits = [time_at(ep, i) for i in find_all(ep['text'], p)] if ep else []
            if not hits:
                R.e(f'{cid}：摘录不在第{pt[0]}集里：{shown[:20]}')
                continue
            near = min(abs(h - pt[1]) for h in hits)
            if n == 0 and near > 30:
                R.e(f'{cid}：定位点与第一条摘录最近的位置相差 {near} 秒')
            if rg and not any(rg[1] - 30 <= h <= rg[2] + 30 for h in hits):
                R.e(f'{cid}：摘录不在所属段内：{shown[:20]}')
        elif doc['marks'] and drg:
            keys = [key_at(doc, i) for i in find_all(doc['text'], p)]
            if not any(in_doc_range(k, drg) for k in keys):
                R.e(f'{cid}：摘录不在所属段内：{shown[:20]}')
            elif n == 0 and dpt and not any(in_doc_range(k, dpt) for k in keys):
                R.e(f'{cid}：第一条摘录不在定位点（{field(c, "定位点")}）内')

    for x in unbacked_numbers(c):
        R.e(f'{cid}：数字 {x} 在摘录和画面识别里都找不到。'
            f'把含这个数字的原句加进原文摘录，或在该行开头标（整理者补充）')

    has_frame = False
    if typ == 'S':
        if not 1 <= c['steps'] <= 7:
            R.e(f'{cid}：路径应为 1 到 7 步，现在读到 {c["steps"]} 步（每步一行，以「1.」这样的序号开头）')
        if not field(c, '预期结果'):
            R.e(f'{cid}：缺预期结果')
        shot = field(c, '截图')
        has_frame = bool(shot) and os.path.isfile(os.path.join(a.series, shot))
        if video and not has_frame:
            R.e(f'{cid}：截图文件不存在：{shot or "未填"}')
        if video and not field(c, '画面识别'):
            R.e(f'{cid}：缺画面识别')
    elif typ:
        concl, more = field(c, '结论'), field(c, '展开')
        if not concl:
            R.e(f'{cid}：缺结论')
        if len(concl) > 40:
            R.e(f'{cid}：结论超过 40 字')
        if len(concl) + len(more) > 160:
            R.e(f'{cid}：结论加展开超过 160 字')

    index.append({'id': c['id'], 'type': typ, 'topic': field(c, '主题'),
                  'title': c['title'], 'status': field(c, '状态'), 'has_frame': has_frame})

for rg, ids in ranges.items():
    if len(ids) > 1:
        R.w(f'{"、".join(ids)} 的所属段完全相同，检查是否重复')

if a.write_index and not R.err:
    out = os.path.join(a.series, 'cards', 'index.json')
    data = {'series': os.path.basename(os.path.normpath(a.series)), 'cards': index}
    json.dump(data, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'已写入 {out}，共 {len(index)} 张卡')

R.done('卡片验收')
