#!/usr/bin/env python3
"""检查脚本和渲染脚本共用的解析函数。"""
import glob
import os
import re
import sys

DASH = r'[–—\-~～至]'
RE_POINT = re.compile(r'第\s*(\d+)\s*集\s*(\d{1,3}):(\d{2})')
RE_RANGE = re.compile(r'第\s*(\d+)\s*集\s*(\d{1,3}):(\d{2})\s*' + DASH + r'\s*(\d{1,3}):(\d{2})')
RE_ID = re.compile(r'^(?:(?!M-)[A-Z]{1,2}-[SFPCXG]-\d{2,3}|M-\d{2,3})$')
RE_ID_ANY = re.compile(r'(?<![A-Za-z0-9])(?:[A-Z]{1,2}-[SFPCXG]-\d{2,3}|M-\d{2,3})(?!\d)')
RE_PAGE = re.compile(r'(?<![A-Za-z])p\.?\s*(\d+)(?:\s*' + DASH + r'\s*(?:p\.?\s*)?(\d+))?')
RE_PAGE_CN = re.compile(r'第\s*(\d+)\s*(?:' + DASH + r'\s*(\d+)\s*)?页')
RE_CHAP = re.compile(r'第\s*(\d+)\s*章(?:\s*§\s*(\d+)(?:\s*' + DASH + r'\s*§?\s*(\d+))?)?')
RE_MARK = re.compile(r'p\.?\s*\d+|第\s*\d+\s*页|第\s*\d+\s*章(?:\s*§\s*\d+)?')
RE_STEP = r'\s*\d+[.、．)）]\s*'
KIND = {'步骤': 'S', '框架': 'F', '原则': 'P', '案例': 'C', '反例': 'X', '术语': 'G'}
NUM_FIELDS = ('目的', '前置', '结论', '展开', '路径', '预期结果', '岔路', '动作', '边界', '反例', '术语')
CN_DIGIT = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9}
CN_UNIT = {'十': 10, '百': 100, '千': 1000}


def norm(s):
    """只留文字和数字，用来比对摘录。"""
    return re.sub(r'[\W_]+', '', s).lower()


def mmss(sec):
    return f'{sec // 60:02d}:{sec % 60:02d}'


def find_all(text, sub):
    out, i = [], text.find(sub)
    while i >= 0:
        out.append(i)
        i = text.find(sub, i + 1)
    return out


# ---------- 视频定位 ----------

def parse_point(s):
    m = RE_POINT.search(s or '')
    return (int(m[1]), int(m[2]) * 60 + int(m[3])) if m else None


def parse_range(s):
    m = RE_RANGE.search(s or '')
    if not m:
        return None
    return (int(m[1]), int(m[2]) * 60 + int(m[3]), int(m[4]) * 60 + int(m[5]))


def load_transcript(path):
    """返回 {集号: {'text': 归一化全文, 'pos': [(字符偏移, 秒)], 'end': 最后时间戳}}。"""
    eps, ep, seq = {}, None, 0
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if line.startswith('# '):
            seq += 1
            m = re.search(r'第\s*(\d+)\s*集', line)
            ep = int(m[1]) if m else seq
            eps.setdefault(ep, {'text': '', 'pos': [], 'end': 0})
            continue
        m = re.match(r'\[(\d{1,3}):(\d{2})(?::(\d{2}))?\]\s*(.*)', line)
        if not m:
            continue
        if ep is None:
            ep = 1
            eps[ep] = {'text': '', 'pos': [], 'end': 0}
        if m[3] is None:
            t = int(m[1]) * 60 + int(m[2])
        else:
            t = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
        e = eps[ep]
        e['pos'].append((len(e['text']), t))
        e['text'] += norm(m[4])
        e['end'] = max(e['end'], t)
    return eps


def time_at(e, offset):
    t = 0
    for off, sec in e['pos']:
        if off > offset:
            break
        t = sec
    return t


# ---------- 文档和书的定位 ----------

def parse_doc_range(s):
    """p.47、p.47–52、第5页、第3章、第3章 §2、第3章 §2–4 → (类别, 起, 止)。"""
    s = s or ''
    m = RE_PAGE.search(s) or RE_PAGE_CN.search(s)
    if m:
        lo = int(m[1])
        hi = int(m[2]) if m[2] else lo
        return ('p', (lo, 0), (max(lo, hi), 0))
    m = RE_CHAP.search(s)
    if m:
        ch = int(m[1])
        if m[2] is None:
            return ('c', (ch, 0), (ch, 9999))
        lo = int(m[2])
        hi = int(m[3]) if m[3] else lo
        return ('c', (ch, lo), (ch, max(lo, hi)))
    return None


def in_doc_range(key, rg):
    return bool(key and rg) and key[0] == rg[0] and rg[1] <= key[1] <= rg[2]


def doc_label(key):
    if key[0] == 'p':
        return f'p.{key[1][0]}'
    return f'第{key[1][0]}章' + (f' §{key[1][1]}' if key[1][1] else '')


def load_doc(path):
    """返回 {'text': 归一化全文, 'marks': [(字符偏移, 定位键)]}。标记写在该页或该节内容之前。"""
    raw = open(path, encoding='utf-8').read()
    text, marks, last = '', [], 0
    for m in re.finditer(r'\[([^\]\n]{1,20})\]', raw):
        if not RE_MARK.fullmatch(m[1].strip()):
            continue
        rg = parse_doc_range(m[1])
        text += norm(raw[last:m.start()])
        marks.append((len(text), (rg[0], rg[1])))
        last = m.end()
    text += norm(raw[last:])
    return {'text': text, 'marks': marks}


def key_at(doc, offset):
    key = None
    for off, k in doc['marks']:
        if off > offset:
            break
        key = k
    return key


def load_source(series_dir):
    """有时间戳行才算视频，否则按文档读。"""
    path = os.path.join(series_dir, 'sources', 'corrected.md')
    eps = load_transcript(path)
    if any(e['pos'] for e in eps.values()):
        return {'video': True, 'eps': eps, 'doc': None,
                'all': ''.join(e['text'] for e in eps.values())}
    doc = load_doc(path)
    return {'video': False, 'eps': {}, 'doc': doc, 'all': doc['text']}


# ---------- 卡片 ----------

def load_card(path):
    card = {'path': path, 'id': '', 'kind': '', 'title': '', 'f': {}, 'steps': 0}
    key = None
    for ln in open(path, encoding='utf-8').read().splitlines():
        m = re.match(r'#+\s*\[([^\]]+)\]\s*([^：:]+)[：:]\s*(.+)', ln)
        if m and not card['id']:
            card['id'], card['kind'], card['title'] = m[1].strip(), m[2].strip(), m[3].strip()
            continue
        m = re.match(r'-\s*([^：:\s]{1,8})[：:]\s*(.*)', ln)
        if m:
            key = m[1]
            card['f'].setdefault(key, []).append(m[2].strip())
            continue
        if key and ln.strip():
            if key == '路径' and re.match(RE_STEP, ln):
                card['steps'] += 1
            card['f'][key][-1] += '\n' + ln.strip()
    return card


def field(card, key):
    return '\n'.join(card['f'].get(key, [])).strip()


def card_type(card):
    parts = card['id'].split('-')
    return parts[1] if len(parts) == 3 else KIND.get(card['kind'], '')


def load_cards(base_dir):
    paths = sorted(glob.glob(os.path.join(base_dir, 'cards', '*.md')))
    return [load_card(p) for p in paths]


def quote_pieces(card):
    """摘录按省略号切开，返回 [(归一化片段, 原样片段)]，短于 6 个字的不算。"""
    out = []
    for q in card['f'].get('原文摘录', []):
        for piece in re.split(r'……|…|\.\.\.', q):
            p = norm(piece)
            if len(p) >= 6:
                out.append((p, piece.strip()))
    return out


def cn2int(s):
    total, sec, num = 0, 0, 0
    for ch in s:
        if ch in CN_DIGIT:
            num = CN_DIGIT[ch]
        elif ch in CN_UNIT:
            sec += (num or 1) * CN_UNIT[ch]
            num = 0
        elif ch == '万':
            total += (sec + num) * 10000
            sec = num = 0
    return total + sec + num


def ints_in(text):
    out = {int(x) for x in re.findall(r'\d+', text)}
    for s in re.findall(r'[零一二两三四五六七八九十百千万]+', text):
        out.add(cn2int(s))
    return out


def unbacked_numbers(card):
    """卡片正文里出现、但摘录和画面识别里都找不到的数字。"""
    ev = ints_in('\n'.join(card['f'].get('原文摘录', []) + card['f'].get('画面识别', [])))
    lines = [card['title']]
    for k in NUM_FIELDS:
        for v in card['f'].get(k, []):
            lines += v.split('\n')
    bad = []
    for ln in lines:
        ln = re.sub('^' + RE_STEP, '', ln)
        if re.match(r'\s*[（(]整理者补充[)）]', ln):
            continue
        for x in re.findall(r'(?<![A-Za-z\d])\d+', ln):
            if int(x) not in ev and x not in bad:
                bad.append(x)
    return bad


# ---------- 表格 ----------

def load_table(path):
    """读文件里的 Markdown 表格，返回字典列表。一个文件只放一张表。"""
    rows, head = [], None
    for ln in open(path, encoding='utf-8'):
        ln = ln.strip()
        if not ln.startswith('|'):
            continue
        cells = [c.strip() for c in ln.strip('|').split('|')]
        if all(re.fullmatch(r':?-{2,}:?', c) for c in cells):
            continue
        if head is None:
            head = cells
            continue
        if len(cells) == len(head):
            rows.append(dict(zip(head, cells)))
    return rows


def glossary_pairs(path):
    """可以机器全局核对的误写。填了「仅限上下文」的行跳过。"""
    out = []
    for r in load_table(path):
        wrong = r.get('误写', '')
        if len(wrong) >= 2 and not r.get('仅限上下文', ''):
            out.append((wrong, r.get('正写', '')))
    return out


def load_topics(path):
    return set(re.findall(r'^##\s+(T\d{2,3})(?!\d)', open(path, encoding='utf-8').read(), re.M))


class Report:
    def __init__(self):
        self.err, self.warn = [], []

    def e(self, msg):
        self.err.append(msg)

    def w(self, msg):
        self.warn.append(msg)

    def done(self, name):
        for m in self.warn:
            print('警告', m)
        for m in self.err:
            print('错误', m)
        print(f'{name}：{len(self.err)} 个错误，{len(self.warn)} 个警告')
        sys.exit(1 if self.err else 0)


def ui_quotes(card, keys=('画面识别',)):
    """取指定字段里被「」括起的文字，按出现顺序去重。默认只取画面识别。"""
    out = []
    for k in keys:
        v = card['f'].get(k, [])
        if isinstance(v, (list, tuple)):
            v = '\n'.join(v)
        for q in re.findall(r'「([^」\n]{2,80})」', v or ''):
            if q not in out:
                out.append(q)
    return out
