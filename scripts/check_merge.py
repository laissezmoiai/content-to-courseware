#!/usr/bin/env python3
"""融合验收：每张原始卡有去向，每张合成卡有来源、有据。
用法：python3 check_merge.py library --write-index
"""
import argparse
import json
import os
import re

from c2c_common import (RE_ID_ANY, Report, card_type, field, load_cards,
                        load_source, load_table, load_topics, quote_pieces,
                        unbacked_numbers)

ap = argparse.ArgumentParser()
ap.add_argument('library')
ap.add_argument('--write-index', action='store_true')
a = ap.parse_args()

R = Report()
lib = a.library
topics = load_topics(os.path.join(lib, 'topic-map.md'))

orig, texts = {}, {}
for r in load_table(os.path.join(lib, 'registry.md')):
    pre, code = r.get('卡片前缀', ''), r.get('系列代号', '')
    d = os.path.join(lib, 'series', code)
    if not pre or not os.path.isfile(os.path.join(d, 'sources', 'corrected.md')):
        continue
    for c in load_cards(d):
        orig[c['id']] = c
    texts[pre] = load_source(d)['all']

merged = {c['id']: c for c in load_cards(os.path.join(lib, 'merged'))}
if not merged:
    R.e('merged/cards/ 里没有合成卡')

# 一、合并日志：每张原始卡恰好登记一次，去向看得懂
logged = {}
for r in load_table(os.path.join(lib, 'merged', 'merge-log.md')):
    cid = r.get('原始卡', '')
    if cid not in orig:
        R.e(f'合并日志：{cid} 不是任何系列里的卡')
        continue
    if cid in logged:
        R.e(f'合并日志：{cid} 登记了两次')
    logged[cid] = r
    m = re.match(r'T\d{2,3}', r.get('主题节点', ''))
    if not m or m[0] not in topics:
        R.e(f'合并日志：{cid} 的主题节点应为主题树里的编号')
    if r.get('关系', '') not in ('重复', '互补', '冲突', '独有'):
        R.e(f'合并日志：{cid} 的关系应为 重复、互补、冲突 或 独有')
    dest = r.get('去向', '')
    mids = [i for i in RE_ID_ANY.findall(dest) if i.startswith('M-')]
    if mids:
        for i in mids:
            if i not in merged:
                R.e(f'合并日志：{cid} 的去向 {i} 不存在')
    elif '附录' in dest:
        pass
    elif '丢弃' in dest:
        if not r.get('说明', ''):
            R.e(f'合并日志：{cid} 丢弃要写说明')
    else:
        R.e(f'合并日志：{cid} 的去向应为合成卡编号、附录或丢弃')
for cid in orig:
    if cid not in logged:
        R.e(f'{cid}：合并日志里没有登记去向')

# 二、合成卡
index = []
for cid, c in merged.items():
    typ = card_type(c)
    if not re.fullmatch(r'M-\d{2,3}', cid):
        R.e(f'{cid or c["path"]}：合成卡编号应为 M-两位序号')
    if typ not in list('SFPCXG'):
        R.e(f'{cid}：标题里的类型应为 步骤、框架、原则、案例、反例 或 术语')
    if field(c, '主题') not in topics:
        R.e(f'{cid}：主题「{field(c, "主题")}」不在主题树里')
    if field(c, '状态') not in ('正文级', '附录级'):
        R.e(f'{cid}：状态应为 正文级 或 附录级')
    review = field(c, '回查')
    if not review:
        R.e(f'{cid}：合成卡要重走一次回查')
    elif re.search(r'无据\s*[1-9]', review):
        R.e(f'{cid}：回查里还有无据的句子')

    srcs = RE_ID_ANY.findall(field(c, '来源卡'))
    if not srcs:
        R.e(f'{cid}：缺来源卡')
    for s in srcs:
        if s not in orig:
            R.e(f'{cid}：来源卡 {s} 不存在')
        elif cid not in RE_ID_ANY.findall(logged.get(s, {}).get('去向', '')):
            R.e(f'{cid}：合并日志里 {s} 的去向没有指向这张卡')
    pres = {s.split('-')[0] for s in srcs if s in orig}

    points = c['f'].get('定位点', [])
    if not points:
        R.e(f'{cid}：缺定位点')
    for p in points:
        m = re.search(r'系列\s*([A-Z]{1,2})', p)
        if len(pres) > 1 and not m:
            R.e(f'{cid}：多个来源时，每行定位点要写（系列 X）')
        elif m and m[1] not in pres:
            R.e(f'{cid}：定位点写的系列 {m[1]} 不在来源卡里')

    pool = [texts[p] for p in pres if p in texts]
    pieces = quote_pieces(c)
    if not pieces:
        R.e(f'{cid}：缺原文摘录')
    for p, shown in pieces:
        if not any(p in t for t in pool):
            R.e(f'{cid}：摘录不是来源系列的校正稿原文：{shown[:20]}')
    for x in unbacked_numbers(c):
        R.e(f'{cid}：数字 {x} 在摘录和画面识别里都找不到')

    if typ == 'S':
        if not 1 <= c['steps'] <= 7:
            R.e(f'{cid}：路径应为 1 到 7 步，现在读到 {c["steps"]} 步')
        if not field(c, '预期结果'):
            R.e(f'{cid}：缺预期结果')
    index.append({'id': cid, 'type': typ, 'topic': field(c, '主题'), 'title': c['title'],
                  'status': field(c, '状态'), 'has_frame': bool(field(c, '截图')),
                  'sources': srcs})

# 三、冲突清单
path = os.path.join(lib, 'merged', 'conflicts.md')
if os.path.isfile(path):
    for r in load_table(path):
        for i in RE_ID_ANY.findall(r.get('已写进', '')):
            if i not in merged:
                R.e(f'冲突 {r.get("编号", "?")}：已写进的 {i} 不存在')

if a.write_index and not R.err:
    out = os.path.join(lib, 'merged', 'cards', 'index.json')
    json.dump({'series': 'merged', 'cards': index}, open(out, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print(f'已写入 {out}，共 {len(index)} 张合成卡')

R.done('融合验收')
