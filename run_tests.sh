#!/usr/bin/env bash
# 最小回归：在全新克隆里可重复跑（自己清现场、重建 testdata 状态）。
# 用法：./run_tests.sh        （在仓库根目录）
set -e
R=testdata/library/series/t-a
L=testdata/library

echo "== [0] 恢复测试初始态（清锁、清卡；卡片在 freeze 后才写入）=="
rm -f "$R"/segments.lock
rm -rf "$R"/cards && mkdir -p "$R"/cards
# 帧识别原文必须比截图新（全新克隆 mtime 归零，统一 touch 一次）
touch "$R/frames/ep01-0040.txt"

echo "== [0.5] 从模板生成 draft.html =="
python3 scripts/gen_draft.py .

echo "== [1] coverage_reverse --freeze（期望 0 错）=="
python3 scripts/coverage_reverse.py "$R" --freeze

echo "== [2] 写入卡片 =="
python3 - <<'PY'
S='testdata/library/series/t-a'
def w(n,t): open(f'{S}/cards/{n}','w',encoding='utf-8').write(t)
w('A-S-01.md',"""## [A-S-01] 步骤：把文件交给 AI 的演示
- 主题：T01
- 状态：正文级
- 路径：
1. 打开工作台主界面
2. 把文件拖进对话窗口
3. 默认模式直接执行
- 预期结果：文件被 AI 接收并直接处理
- 截图：frames/ep01-0040.jpg
- 画面识别：主界面按钮「开始执行」；输入框提示「分享你的想法」
- 定位点：第1集 00:29
- 所属段：第1集 00:29-00:59
- 原文摘录：「第一种方式直接把文件拖进窗口」
- 回查：逐句核对完成，无据 0
""")
w('A-P-01.md',"""## [A-P-01] 原则：先想清楚再动手
- 主题：T01
- 状态：正文级
- 结论：先想清楚再动手，按原则选模式
- 展开：什么情况用哪种模式要看任务本身，按固定原则判断就不会乱
- 动作：动手前先明确任务类型
- 边界：简单问题不需要
- 定位点：第1集 00:59
- 所属段：第1集 00:59-01:29
- 原文摘录：「原则是先想清楚再动手」「按这个原则选模式就不会乱」
- 回查：逐句核对完成，无据 0
""")
w('A-X-01.md',"""## [A-X-01] 反例：把导航做成装饰
- 主题：T02
- 状态：正文级
- 结论：把导航做成装饰是常见错误
- 展开：导航有明确功能定位，只追求好看会破坏可用性
- 定位点：第1集 01:29
- 所属段：第1集 01:29-02:00
- 原文摘录：「把导航做成装饰是常见错误」
- 回查：逐句核对完成，无据 0
""")
w('A-G-01.md',"""## [A-G-01] 术语：工作模式
- 主题：T01
- 状态：附录级
- 结论：模式是工作方式的预设档位
- 展开：课程把按场景预设的工作方式称作模式，本集讲三种
- 定位点：第1集 00:05
- 所属段：第1集 00:00-00:29
- 原文摘录：「今天我们讲三种工作模式的区别」
- 回查：逐句核对完成，无据 0
""")
print('4 张卡已写入')
PY

echo "== [3] check_cards（期望 0 错 0 警）=="
python3 scripts/check_cards.py "$R" --topic-map "$L/topic-map.md" --prefix A --write-index

echo "== [4] check_frames（期望 0 错 0 警）=="
python3 scripts/check_frames.py "$R"

echo "== [5] coverage_reverse 验收模式（输出必须有「覆盖率：」行；期望 0 错）=="
python3 scripts/coverage_reverse.py "$R"

echo "== [6] render_cards（期望 0 错）=="
python3 scripts/render_cards.py "$R/draft.html" --cards "$R" --registry "$L/registry.md" --out "$R/courseware.html"

echo "== [7] check_courseware（期望 0 错）=="
python3 scripts/check_courseware.py "$R/courseware.html" --registry "$L/registry.md" --glossary "$L/glossary.md" --index "$R/cards/index.json"

echo "== [8] 反例1：摘录非逐字 =="
python3 - <<'PY'
p='testdata/library/series/t-a/cards/A-P-01.md'
s=open(p).read().replace('先想清楚再动手','先想清楚再做事情')
open(p,'w').write(s)
PY
if python3 scripts/check_cards.py "$R" --topic-map "$L/topic-map.md" --prefix A 2>&1 | grep -q "摘录不是校正稿原文"; then echo "✓ 反例1 拦截成功（摘录不是校正稿原文）"; else echo "✗ 反例1 未拦截"; exit 1; fi
python3 - <<'PY'
p='testdata/library/series/t-a/cards/A-P-01.md'
s=open(p).read().replace('先想清楚再做事情','先想清楚再动手')
open(p,'w').write(s)
PY

echo "== [9] 反例2：数字无据 =="
python3 - <<'PY'
p='testdata/library/series/t-a/cards/A-P-01.md'
s=open(p).read().replace('- 边界：简单问题不需要','- 边界：3 种场景外不适用')
open(p,'w').write(s)
PY
if python3 scripts/check_cards.py "$R" --topic-map "$L/topic-map.md" --prefix A 2>&1 | grep -q "数字 3 在摘录和画面识别里都找不到"; then echo "✓ 反例2 拦截成功（数字无据）"; else echo "✗ 反例2 未拦截"; exit 1; fi
python3 - <<'PY'
p='testdata/library/series/t-a/cards/A-P-01.md'
s=open(p).read().replace('- 边界：3 种场景外不适用','- 边界：简单问题不需要')
open(p,'w').write(s)
PY

echo "== [10] 反例3：演示段缺帧 =="
python3 - <<'PY'
s=open('testdata/library/series/t-a/coverage.md').read().replace('| 00:40 | A-S-01 |','| — | A-S-01 |')
open('testdata/library/series/t-a/coverage.md','w').write(s)
PY
if python3 scripts/coverage_reverse.py "$R" 2>&1 | grep -q "依据帧没填。演示段至少一张"; then echo "✓ 反例3 拦截成功（演示段缺帧）"; else echo "✗ 反例3 未拦截"; exit 1; fi
python3 - <<'PY'
s=open('testdata/library/series/t-a/coverage.md').read().replace('| — | A-S-01 |','| 00:40 | A-S-01 |')
open('testdata/library/series/t-a/coverage.md','w').write(s)
PY

echo "== [11] 改稿降级实测（期望 0 错 + 自动改道警告）=="
python3 - <<'PY'
p='testdata/library/series/t-a/cards/A-X-01.md'
s=open(p).read().replace('- 状态：正文级','- 状态：附录级',1)
open(p,'w').write(s)
PY
python3 scripts/check_cards.py "$R" --topic-map "$L/topic-map.md" --prefix A --write-index
python3 scripts/render_cards.py "$R/draft.html" --cards "$R" --registry "$L/registry.md" --out "$R/courseware.html"
python3 scripts/check_courseware.py "$R/courseware.html" --registry "$L/registry.md" --glossary "$L/glossary.md" --index "$R/cards/index.json"
python3 - <<'PY'
p='testdata/library/series/t-a/cards/A-X-01.md'
s=open(p).read().replace('- 状态：附录级','- 状态：正文级',1)
open(p,'w').write(s)
PY
python3 scripts/check_cards.py "$R" --topic-map "$L/topic-map.md" --prefix A --write-index >/dev/null
python3 scripts/render_cards.py "$R/draft.html" --cards "$R" --registry "$L/registry.md" --out "$R/courseware.html" >/dev/null
echo "== 仓库已回到一致态 =="
echo "== 全部通过 =="
