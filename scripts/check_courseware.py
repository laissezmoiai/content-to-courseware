#!/usr/bin/env python3
"""出片自检。
用法：python3 check_courseware.py 课件.html --registry library/registry.md \
        --glossary library/glossary.md --index library/series/wb-a/cards/index.json [--doc]
"""
import argparse
import json
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

from c2c_common import RE_ID, RE_POINT, Report, glossary_pairs, load_table

VOID = {'img', 'br', 'hr', 'meta', 'link', 'input', 'source', 'col', 'wbr'}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.lessons, self.cards = [], [], []
        self.nums, self.blocks, self.appx = {}, set(), set()
        self.lesson = self.card = self.buf = None
        self.figs, self.sourcing = 0, ''

    def handle_starttag(self, tag, attrs):
        at = dict(attrs)
        cls = set((at.get('class') or '').split())
        kind = None
        if tag == 'section' and 'lesson' in cls:
            self.lesson = {'id': at.get('id', '?'), 'goal': False, 'practice': False}
            self.lessons.append(self.lesson)
            kind = 'lesson'
        elif tag == 'article' and 'card' in cls:
            self.card = {'id': at.get('data-id', ''), 'type': at.get('data-type', ''),
                         'title': '', 'links': [], 'figs': 0, 'caps': []}
            self.cards.append(self.card)
            kind = 'card'
        elif tag == 'h3' and self.card is not None:
            self.buf, kind = [], 'h3'
        elif tag == 'a' and 'src' in cls and self.card is not None:
            self.buf, kind = [], ('src', at.get('href', ''))
        elif tag == 'figcaption' and self.card is not None:
            self.buf, kind = [], 'cap'
        elif at.get('id') in ('n-lessons', 'n-cards', 'n-figures'):
            self.buf, kind = [], ('num', at['id'])
        elif 'sourcing' in cls:
            self.buf, kind = [], 'sourcing'
        if tag == 'li' and at.get('data-id'):
            self.appx.add(at['data-id'])
        if tag == 'figure':
            self.figs += 1
            if self.card is not None:
                self.card['figs'] += 1
        if self.lesson is not None:
            if 'goal' in cls:
                self.lesson['goal'] = True
            if 'practice' in cls:
                self.lesson['practice'] = True
        self.blocks |= cls & {'route', 'cheatsheet', 'appendix'}
        if tag not in VOID:
            self.stack.append((tag, kind))

    def handle_endtag(self, tag):
        if tag not in [t for t, _ in self.stack]:
            return
        while self.stack:
            t, k = self.stack.pop()
            if k == 'lesson':
                self.lesson = None
            elif k == 'card':
                self.card = None
            elif k:
                txt = ''.join(self.buf or []).strip()
                self.buf = None
                if k == 'cap':
                    if self.card is not None:
                        self.card['caps'].append(txt)
                elif k == 'h3':
                    if self.card is not None:
                        self.card['title'] = txt
                elif k == 'sourcing':
                    self.sourcing = txt
                elif k[0] == 'src':
                    if self.card is not None:
                        self.card['links'].append((k[1], txt))
                elif k[0] == 'num':
                    self.nums[k[1]] = txt
            if t == tag:
                break

    def handle_data(self, data):
        if self.buf is not None:
            self.buf.append(data)


ap = argparse.ArgumentParser()
ap.add_argument('html')
ap.add_argument('--registry')
ap.add_argument('--glossary')
ap.add_argument('--index', nargs='*', default=[])
ap.add_argument('--doc', action='store_true')
a = ap.parse_args()

R = Report()
raw = open(a.html, encoding='utf-8').read()
text = re.sub(r'"data:[^"]*"', '""', raw)
pg = Page()
pg.feed(text)


def num(key):
    m = re.search(r'\d+', pg.nums.get(key, ''))
    return int(m[0]) if m else None


for key, actual, label in (('n-lessons', len(pg.lessons), '节数'),
                           ('n-cards', len(pg.cards), '卡片数'),
                           ('n-figures', pg.figs, '配图数')):
    if num(key) != actual:
        R.e(f'封面{label}写的是 {num(key)}，正文实际是 {actual}')
plain = re.sub(r'<[^>]+>', '', text)
for m in re.finditer(r'(\d+)\s*张(?:知识)?卡', plain):
    if int(m[1]) != len(pg.cards):
        R.e(f'页面里写了「{m[0]}」，正文实际是 {len(pg.cards)} 张')

prefixes = None
if a.registry:
    prefixes = {r.get('卡片前缀', '') for r in load_table(a.registry)}

seen = set()
for c in pg.cards:
    cid = c['id'] or '（无编号）'
    if not RE_ID.match(c['id']):
        R.e(f'{cid}：编号格式不对')
    elif prefixes is not None and not c['id'].startswith('M-') and c['id'].split('-')[0] not in prefixes:
        R.e(f'{cid}：前缀不在登记表里')
    if c['id'] in seen:
        R.e(f'{cid}：编号重复')
    seen.add(c['id'])
    if c['type'] not in list('SFPCXG'):
        R.e(f'{cid}：data-type 应为 S F P C X G 之一')
    if a.doc:
        continue
    if not c['links']:
        R.e(f'{cid}：没有出处链接')
    for href, txt in c['links']:
        m = RE_POINT.search(txt)
        if not m:
            R.e(f'{cid}：出处文字应为「第N集 mm:ss」，现在是「{txt}」')
            continue
        ep, sec = int(m[1]), int(m[2]) * 60 + int(m[3])
        q = parse_qs(urlparse(href).query)
        t = re.sub(r'\D', '', q.get('t', [''])[0])
        if t == '' or int(t) != sec:
            R.e(f'{cid}：链接的 t 应为 {sec}（{txt}）')
        if 'bilibili.com' in href and q.get('p', ['1'])[0] != str(ep):
            R.e(f'{cid}：链接的 p 应为 {ep}（{txt}）')
    if c['type'] == 'S':
        if c['figs'] < 1:
            R.e(f'{cid}：步骤卡没有截图')
        elif not any(RE_POINT.search(x) for x in c['caps']):
            R.e(f'{cid}：图注要写到「第N集 mm:ss」')

if a.index:
    want = {}
    for p in a.index:
        for x in json.load(open(p, encoding='utf-8'))['cards']:
            want[x['id']] = x
    for cid, x in want.items():
        if x['status'] == '正文级' and cid not in seen:
            R.e(f'{cid}：正文级的卡没有出现在正文')
        if x['status'] == '附录级' and cid not in pg.appx:
            R.e(f'{cid}：附录级的卡没有列进附录')
    for c in pg.cards:
        x = want.get(c['id'])
        if x is None:
            R.e(f'{c["id"]}：不在卡片索引里')
        elif x['status'] != '正文级':
            R.e(f'{c["id"]}：附录级的卡出现在正文')
        elif x['title'].strip() != c['title']:
            R.e(f'{c["id"]}：标题与卡片文件不一致，课件要用 render_cards.py 生成')

for s in pg.lessons:
    if not s['goal']:
        R.e(f'{s["id"]} 节：没有目标句')
    if not s['practice']:
        R.e(f'{s["id"]} 节：没有练习')
for block, label in (('route', '精华路线'), ('cheatsheet', '速查清单'), ('appendix', '附录')):
    if block not in pg.blocks:
        R.e(f'缺{label}')
if not re.search(r'\d', pg.sourcing):
    R.e('缺带数字的取材说明')

for bad in ('〔?〕', '〔？〕', 'TODO', '<!--CARD', '<!--APPENDIX-CARDS-->'):
    if bad in text:
        R.e(f'残留 {bad}')
if a.glossary:
    for wrong, right in glossary_pairs(a.glossary):
        if wrong in text:
            R.e(f'残留误写「{wrong}」，应为「{right}」')

R.done('出片自检')
