#!/usr/bin/env python3
"""把卡片文件渲染进课件草稿。卡片内容不经过手写，封面数字由脚本数出来。
用法：python3 render_cards.py 草稿.html --cards library/series/wb-a \
        --registry library/registry.md --out library/series/wb-a/courseware.html
融合课件把 --cards 换成 library/merged。
"""
import argparse
import base64
import html
import json
import mimetypes
import os
import re

from c2c_common import (RE_STEP, Report, card_type, field, load_cards,
                        load_table, parse_doc_range, parse_point)

TAGS = {'S': '照着做', 'F': '想清楚', 'P': '原则', 'C': '案例', 'X': '反例', 'G': '术语'}
SHOW = ('目的', '前置', '结论', '展开', '路径', '预期结果', '岔路', '动作', '边界', '反例')
STEPS_CLASS = 'steps'

ap = argparse.ArgumentParser()
ap.add_argument('draft')
ap.add_argument('--cards', required=True)
ap.add_argument('--registry', required=True)
ap.add_argument('--out', required=True)
a = ap.parse_args()

R = Report()
lib = os.path.dirname(os.path.abspath(a.registry))
series = {}
for r in load_table(a.registry):
    if r.get('卡片前缀'):
        series[r['卡片前缀']] = (os.path.join(lib, 'series', r.get('系列代号', '')),
                                r.get('来源链接', ''))
cards = {c['id']: c for c in load_cards(a.cards)}
page = open(a.draft, encoding='utf-8').read()
if re.search(r'<article[^>]*class="[^"]*\bcard\b', page):
    R.e('草稿里有手写的卡片，改成 <!--CARD 编号--> 占位')

ep_links = {}


def link_for(prefix, ep, sec):
    sdir, base = series.get(prefix, ('', ''))
    if prefix not in ep_links:
        p = os.path.join(sdir, 'sources', 'episodes.json')
        ep_links[prefix] = json.load(open(p, encoding='utf-8')) if os.path.isfile(p) else {}
    u = ep_links[prefix].get(str(ep), '')
    if u:
        return u + ('&' if '?' in u else '?') + f't={sec}'
    if 'bilibili.com' in base:
        return base.split('?')[0].rstrip('/') + f'?p={ep}&t={sec}'
    if base:
        return base + ('&' if '?' in base else '?') + f't={sec}'
    return ''


def sources(card):
    """返回 [(链接, 显示文字)]。文档类链接为空。"""
    out = []
    own = card['id'].split('-')[0]
    for line in card['f'].get('定位点', []):
        pt = parse_point(line)
        if pt:
            m = re.search(r'系列\s*([A-Z]{1,2})', line)
            prefix = m[1] if m else own
            txt = f'第{pt[0]}集 {pt[1] // 60:02d}:{pt[1] % 60:02d}'
            if m:
                txt += f'（系列 {m[1]}）'
            href = link_for(prefix, pt[0], pt[1])
            if not href:
                R.e(f'{card["id"]}：登记表里找不到系列 {prefix} 的来源链接')
            out.append((href, txt))
        elif parse_doc_range(line):
            out.append(('', line.strip()))
    return out


def find_image(card, shot):
    dirs = [a.cards, lib] + [d for d, _ in series.values()]
    for d in dirs:
        p = os.path.join(d, shot)
        if os.path.isfile(p):
            return p
    return None


def shot_time(shot):
    m = re.search(r'ep(\d+)-(\d{2,3})(\d{2})\.', os.path.basename(shot))
    return f'第{int(m[1])}集 {m[2]}:{m[3]}' if m else ''


def esc(s):
    return html.escape(s, quote=True)


placed, figs = [], 0


def render(card):
    global figs
    cid, typ = card['id'], card_type(card)
    out = [f'<article class="card" id="{cid}" data-id="{cid}" data-type="{typ}">',
           f'  <div class="cap"><span class="tag">{TAGS.get(typ, "")}</span>'
           f'<span class="cid">{cid}</span></div>',
           f'  <h3>{esc(card["title"])}</h3>']
    for k in SHOW:
        v = field(card, k)
        if not v:
            continue
        if k == '路径':
            steps = [re.sub('^' + RE_STEP, '', x) for x in v.split('\n') if x.strip()]
            items = ''.join(f'<li>{esc(x)}</li>' for x in steps)
            out.append(f'  <ol class="{STEPS_CLASS}">{items}</ol>')
        else:
            out.append(f'  <p class="row"><b>{k}</b>{esc(v)}</p>')
    srcs = sources(card)
    if not srcs:
        R.e(f'{cid}：定位点读不出来')
    shot = field(card, '截图')
    if shot:
        path = find_image(card, shot)
        if not path:
            R.e(f'{cid}：截图文件不存在：{shot}')
        else:
            figs += 1
            mime = mimetypes.guess_type(path)[0] or 'image/jpeg'
            data = base64.b64encode(open(path, 'rb').read()).decode()
            when = shot_time(shot) or (srcs[0][1] if srcs else '')
            out.append(f'  <figure><img src="data:{mime};base64,{data}" alt="{esc(card["title"])}">'
                       f'<figcaption>图 {figs}｜{esc(card["title"])}，{when}</figcaption></figure>')
    for href, txt in srcs:
        if href:
            out.append(f'  <a class="src" href="{esc(href)}">{esc(txt)}</a>')
        else:
            out.append(f'  <span class="src">{esc(txt)}</span>')
    out.append('</article>')
    return '\n'.join(out)


def put(m):
    cid = m[1]
    if cid not in cards:
        R.e(f'占位 {cid}：卡片不存在')
        return m[0]
    if cid in placed:
        R.e(f'{cid}：在草稿里放了两次')
        return ''
    if field(cards[cid], '状态') != '正文级':
        R.e(f'{cid}：附录级的卡不能放进正文')
        return ''
    placed.append(cid)
    return render(cards[cid])


page = re.sub(r'<!--\s*CARD\s+([A-Z0-9\-]+)\s*-->', put, page)

appendix = []
for cid, c in cards.items():
    status = field(c, '状态')
    if status == '正文级' and cid not in placed:
        R.e(f'{cid}：正文级的卡没有放进草稿')
    elif status == '附录级':
        tail = ''.join(f' <a href="{esc(h)}">{esc(t)}</a>' if h else f' {esc(t)}'
                       for h, t in sources(c))
        appendix.append(f'<li data-id="{cid}">{esc(c["title"])}{tail}</li>')
if '<!--APPENDIX-CARDS-->' in page:
    page = page.replace('<!--APPENDIX-CARDS-->', '\n'.join(appendix))
elif appendix:
    R.e('有附录级的卡，但草稿里没有 <!--APPENDIX-CARDS--> 占位')


def fill(text, key, n):
    return re.sub(r'(<[^>]*\bid="%s"[^>]*>)[^<]*' % key, lambda m: m[1] + str(n), text, count=1)


lessons = len(re.findall(r'<section[^>]*class="[^"]*\blesson\b', page))
page = fill(page, 'n-lessons', lessons)
page = fill(page, 'n-cards', len(placed))
page = fill(page, 'n-figures', len(re.findall(r'<figure\b', page)))

if not R.err:
    open(a.out, 'w', encoding='utf-8').write(page)
    print(f'已写入 {a.out}：{lessons} 节，{len(placed)} 张卡，{figs} 张图，附录 {len(appendix)} 张')
R.done('渲染')
