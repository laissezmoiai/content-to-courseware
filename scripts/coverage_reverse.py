#!/usr/bin/env python3
"""覆盖率反向核对。视频和文档都能用，按 corrected.md 里有没有时间戳自动判断。
用法：
  阶段 1 结束（抽卡之前）：python3 coverage_reverse.py library/series/wb-a --freeze
  验收：                    python3 coverage_reverse.py library/series/wb-a
  确需重新切段：            python3 coverage_reverse.py library/series/wb-a --refreeze "原因"
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import subprocess

from c2c_common import (RE_ID_ANY, Report, doc_label, field, find_all,
                        in_doc_range, key_at, load_cards, load_source,
                        load_table, mmss, parse_doc_range, parse_range,
                        quote_pieces, time_at)

GAP = 15        # 允许的空档秒数
TOL = 10        # 摘录落在段内的容差秒数
MAX_SEG = 120   # 一段超过这么多秒，冻结时警告
MAX_CHAT = 60   # 寒暄段超过这么多秒，冻结时警告
MIN_SEG = 30    # 非片尾段短于这么多秒，冻结时警告
KINDS = ('演示', '讲解', '寒暄')

ap = argparse.ArgumentParser()
ap.add_argument('series')
g = ap.add_mutually_exclusive_group()
g.add_argument('--freeze', action='store_true')
g.add_argument('--refreeze', metavar='原因')
a = ap.parse_args()

R = Report()
LOCK = os.path.join(a.series, 'segments.lock')
rows = load_table(os.path.join(a.series, 'coverage.md'))
cards = {c['id']: c for c in load_cards(a.series)}
src = load_source(a.series)
video, eps, doc = src['video'], src['eps'], src['doc']
if not rows:
    R.e('coverage.md 里没有读到表格')
if not video and not doc['marks']:
    R.e('corrected.md 里既没有时间戳，也没有页码或章节标记，无法核对覆盖')


def row_range(r):
    s = r.get('定位', '')
    return parse_range(s) if video else parse_doc_range(s)


def canon(rg):
    """切段边界的规范写法，只含数字，空格和连接符怎么写都不影响。"""
    if video:
        return f'{rg[0]}:{rg[1]}-{rg[2]}'
    return f'{rg[0]}:{rg[1][0]}.{rg[1][1]}-{rg[2][0]}.{rg[2][1]}'


def ev_frames(cell, ep):
    """把「依据帧」单元格解析成 [(MM, SS)]，顺带返回格式错误说明。"""
    out, bad = [], []
    for tok in re.split(r'[、,，\s]+', (cell or '').strip()):
        if not tok or tok in ('—', '-'):
            continue
        m = re.fullmatch(r'(\d{1,3}):(\d{2})', tok)
        if not m:
            bad.append(f'「{tok}」不是 MM:SS')
            continue
        if int(m[2]) >= 60:
            bad.append(f'「{tok}」的秒不小于 60')
            continue
        out.append((int(m[1]), int(m[2])))
    return out, bad


def probe(path):
    try:
        out = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', path],
            capture_output=True, text=True, timeout=30).stdout.strip()
        return int(float(out))
    except Exception:
        return None


def durations():
    """每集实际时长：先读视频文件，读不到才退回转写稿最后一句的时间。"""
    out, weak = {}, []
    for ep, e in sorted(eps.items()):
        sec = probe(os.path.join(a.series, 'sources', 'media', f'{ep:02d}.mp4'))
        if sec is None:
            sec = e['end']
            weak.append(ep)
        out[str(ep)] = sec
    return out, weak


def check_gaps(by_ep, ends, strict=False):
    lim = 0 if strict else GAP
    for ep in sorted(ends, key=int):
        end, cur = ends[ep], 0
        for s, t in sorted(by_ep.get(int(ep), [])):
            if s < cur:
                R.e(f'第{ep}集 {mmss(s)} 起的一段与前一段重叠（前一段到 {mmss(cur)}）')
            elif s - cur > lim:
                R.e(f'第{ep}集 {mmss(cur)}–{mmss(s)} 没有登记在矩阵里')
            cur = max(cur, t)
        if end - cur > GAP:
            R.e(f'第{ep}集 {mmss(cur)}–{mmss(end)} 没有登记在矩阵里')
        if cur - end > GAP:
            R.e(f'第{ep}集矩阵写到 {mmss(cur)}，超过该集时长 {mmss(end)}')
    for ep in sorted(by_ep):
        if str(ep) not in ends:
            R.e(f'矩阵里的第{ep}集不在素材里')


def covered(s, e, intervals):
    n, cur = 0, s
    for x, y in sorted(intervals):
        x, y = max(x, cur), min(y, e)
        if y > x:
            n += y - x
            cur = y
    return n


def check_ev(r, name, rg):
    """依据帧：必须填、必须落在本段内、帧和识别原文都要在。冻结和验收各调一次。"""
    cell = (r.get('依据帧') or '').strip()
    frames, bad = ev_frames(cell, rg[0])
    for b in bad:
        R.e(f'{name}：依据帧{b}')
    kind = (r.get('性质', '') or '').strip()
    if not frames and not bad:
        if kind == '演示':
            R.e(f'{name}：依据帧没填。演示段至少一张落在本段内的帧')
        elif kind == '讲解':
            R.w(f'{name}：讲解段没填依据帧（讲解可只凭口播，填了便于回查画面）')
        return
    for mm, ss in frames:
        t = mm * 60 + ss
        if not rg[1] <= t < rg[2]:
            R.e(f'{name}：依据帧 {mm:02d}:{ss:02d} 不在本段'
                f'（{mmss(rg[1])}–{mmss(rg[2])}，左闭右开）内')
            continue
        jpg = os.path.join(a.series, 'frames', f'ep{rg[0]:02d}-{mm:02d}{ss:02d}.jpg')
        txt = os.path.splitext(jpg)[0] + '.txt'
        if not os.path.isfile(jpg):
            R.e(f'{name}：依据帧文件不存在 {os.path.relpath(jpg, a.series)}')
        elif not os.path.isfile(txt):
            R.e(f'{name}：依据帧缺识别原文 {os.path.relpath(txt, a.series)}')
        elif len(re.sub(r'\s+', '', open(txt, encoding='utf-8').read())) < 20:
            R.e(f'{name}：依据帧的识别原文是空的 {os.path.relpath(txt, a.series)}')


def hit_video(card, ep, rg):
    for p, _ in quote_pieces(card):
        for i in find_all(ep['text'], p):
            if rg[1] - TOL <= time_at(ep, i) <= rg[2] + TOL:
                return True
    return False


def hit_doc(card, rg):
    for p, _ in quote_pieces(card):
        for i in find_all(doc['text'], p):
            if in_doc_range(key_at(doc, i), rg):
                return True
    return False


# ---------- 切段指纹 ----------

segs, by_ep = {}, {}
for r in rows:
    rg = row_range(r)
    if rg:
        segs[canon(rg)] = r.get('定位', '').strip()
        if video:
            by_ep.setdefault(rg[0], []).append((rg[1], rg[2]))
sha = hashlib.sha256(json.dumps(sorted(segs)).encode()).hexdigest()[:16]

if a.freeze or a.refreeze:
    old = json.load(open(LOCK, encoding='utf-8')) if os.path.isfile(LOCK) else None
    if a.freeze and old:
        R.e('已经冻结过。确需重新切段，用 --refreeze "原因"')
    if a.freeze and cards:
        R.e(f'cards/ 里已有 {len(cards)} 张卡，不能按「先切段后抽卡」冻结。'
            f'确需补冻结，用 --refreeze "原因"，记录里会注明当时已有卡片')
    for r in rows:
        name, kind = r.get('段', '?'), r.get('性质', '')
        rg = row_range(r)
        if not rg:
            R.e(f'{name}：定位读不出来：{r.get("定位", "")}')
            continue
        if not r.get('讲了什么', '').strip():
            R.e(f'{name}：「讲了什么」没填。切段要按素材内容写，不能按卡片写')
        if kind not in KINDS:
            R.e(f'{name}：性质应为 演示、讲解 或 寒暄')
        if video:
            check_ev(r, name, rg)
            n = rg[2] - rg[1]
            if kind == '寒暄' and n > MAX_CHAT:
                R.w(f'{name}：寒暄段长 {n} 秒，检查里面有没有讲解或演示')
            elif kind != '寒暄' and n > MAX_SEG:
                R.w(f'{name}：这一段长 {n} 秒，检查是否该再切')
            if kind != '寒暄' and n < MIN_SEG:
                R.w(f'{name}：这一段只有 {n} 秒，短于 {MIN_SEG} 秒，'
                    f'检查是否该并入相邻段')
    ends, weak = durations() if video else ({}, [])
    if video:
        check_gaps(by_ep, ends, strict=True)
    if weak:
        R.w(f'第 {"、".join(map(str, weak))} 集读不到视频文件，时长取自转写稿最后一句，'
            f'片尾不说话的部分核对不到')
    if R.err:
        R.done('切段冻结')
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    entry = {'指纹': sha, '段数': len(segs), '总时长': sum(ends.values()),
             '卡片数': len(cards), '原因': a.refreeze or '首次冻结', '时间': now}
    lock = {'指纹': sha, '切段': segs, '时长': ends, '时长靠转写稿的集': weak,
            '历史': (old or {}).get('历史', []) + [entry]}
    json.dump(lock, open(LOCK, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    if a.refreeze:
        logs = sorted(glob.glob(os.path.join(a.series, 'runlog-*.md')))
        if logs:
            before = old['历史'][-1]['段数'] if old else '无'
            with open(logs[-1], 'a', encoding='utf-8') as f:
                f.write(f'\n- 重新冻结切段（{now}）：{a.refreeze}；'
                        f'段数 {before} → {len(segs)}；当时已有 {len(cards)} 张卡\n')
    print(f'已写入 {LOCK}：{len(segs)} 段，指纹 {sha}')
    R.done('切段冻结')

# ---------- 验收 ----------

lock = None
if not os.path.isfile(LOCK):
    R.e('没有 segments.lock：阶段 1 结束时没有冻结切段（--freeze）')
else:
    lock = json.load(open(LOCK, encoding='utf-8'))
    if lock['指纹'] != sha:
        gone = [v for k, v in lock['切段'].items() if k not in segs]
        new = [v for k, v in segs.items() if k not in lock['切段']]
        R.e(f'切段在冻结之后被改过。消失：{"；".join(gone) or "无"}。'
            f'新增：{"；".join(new) or "无"}。确需改，用 --refreeze "原因"')
    if lock['历史'][0].get('卡片数'):
        R.w(f'这份矩阵首次冻结时已有 {lock["历史"][0]["卡片数"]} 张卡，'
            f'不能证明切段先于抽卡')
    if lock.get('时长靠转写稿的集'):
        R.w('部分集的时长取自转写稿，片尾不说话的部分核对不到')

doc_rows, used, total, ok = [], set(), 0, 0
for r in rows:
    name, kind = r.get('段', '?'), r.get('性质', '')
    dest, why = r.get('去向', ''), r.get('理由', '')
    rg = row_range(r)
    if not rg:
        want = '「第N集 mm:ss–mm:ss」' if video else '「p.47–52」或「第3章 §2」'
        R.e(f'{name}：定位格式应为{want}')
        continue
    if not video:
        same = [k[1] for _, k in doc['marks'] if k[0] == rg[0]]
        last = max(same) if same else None
        if last is None:
            R.e(f'{name}：定位的写法与校正稿里的标记不是同一种')
            continue
        if rg[1] > last or (rg[2][1] != 9999 and rg[2] > last):
            R.e(f'{name}：定位超出校正稿最后的位置（{doc_label((rg[0], last))}），'
                f'检查是数字写错还是校正稿被截断')
            continue
        doc_rows.append(rg)
    if video:
        check_ev(r, name, rg)
    if kind not in KINDS:
        R.e(f'{name}：性质应为 演示、讲解 或 寒暄')
        continue
    counts = kind != '寒暄'
    total += counts
    if not dest:
        R.e(f'{name}：去向没填')
        continue

    ids = RE_ID_ANY.findall(dest)
    if ids:
        missing = [i for i in ids if i not in cards]
        for i in missing:
            R.e(f'{name}：去向里的 {i} 不存在')
        if missing:
            continue
        used.update(ids)
        if video:
            ep = eps.get(rg[0])
            if not ep:
                R.e(f'{name}：第{rg[0]}集不在校正稿里')
                continue
            intervals = []
            for i in ids:
                cr = parse_range(field(cards[i], '所属段'))
                if cr and cr[0] == rg[0]:
                    intervals.append((cr[1], cr[2]))
            if covered(rg[1], rg[2], intervals) < 0.5 * (rg[2] - rg[1]):
                R.e(f'{name}：{"、".join(ids)} 的所属段没有盖住这一段'
                    f'（第{rg[0]}集 {mmss(rg[1])}–{mmss(rg[2])}）')
                continue
            hit = any(hit_video(cards[i], ep, rg) for i in ids)
        else:
            hit = any(hit_doc(cards[i], rg) for i in ids)
        if hit:
            ok += counts
        else:
            R.e(f'{name}：{"、".join(ids)} 没有一条摘录落在这一段。'
                f'补一条本段的摘录，或把去向改成附录')
    elif '附录' in dest:
        ok += counts
    elif '丢弃' in dest:
        if kind == '演示':
            R.e(f'{name}：演示段不许丢弃，放不下就进附录')
        elif kind == '讲解' and not re.search('重复|无关', why):
            R.e(f'{name}：讲解段丢弃的理由只能是重复或无关')
        else:
            ok += counts
    else:
        R.e(f'{name}：去向「{dest}」看不懂，应为卡片编号、附录或丢弃')

if video:
    ends = (lock or {}).get('时长') or {str(ep): e['end'] for ep, e in eps.items()}
    check_gaps(by_ep, ends)
else:
    lost = []
    for _, key in doc['marks']:
        if key not in lost and not any(in_doc_range(key, rg) for rg in doc_rows):
            lost.append(key)
    for key in lost:
        R.e(f'{doc_label(key)} 没有登记在矩阵里')

for cid, c in cards.items():
    if cid not in used and field(c, '状态') == '正文级':
        R.w(f'{cid} 没有被矩阵里任何一段引用')

pct = f'{100 * ok / total:.0f}%' if total else '无'
print(f'覆盖率：{ok}/{total}（{pct}）')
R.done('覆盖率核对')
