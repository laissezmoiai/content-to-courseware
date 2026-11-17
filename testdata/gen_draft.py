import os, sys
root = sys.argv[1] if len(sys.argv) > 1 else '.'
series = os.path.join(root, 'testdata/library/series/t-a')
NL = chr(10)
tpl = open(os.path.join(root, 'templates/courseware.html'), encoding='utf-8').read()
d = tpl.replace('<!--CARD A-P-01-->', '<!--CARD A-S-01-->' + NL + '<!--CARD A-P-01-->' + NL + '<!--CARD A-X-01-->')
pairs = [('<title>课件标题</title>', '<title>t-a 测试课件</title>'),
         ('<h1>课件标题</h1>', '<h1>WorkBuddy 测试课件</h1>'),
         ('第一节标题', '三种工作模式'),
         ('学完你能做到：……', '学完你能说出三种模式的区别并选对模式'),
         ('<p>练习：……</p>', '<p>练习：如果任务是把文件分类，你会用哪种模式？</p>'),
         ('<p>速查：……</p>', '<p>速查：动手前先想清楚再选模式。</p>'),
         ('<li>开场 <a class="src" href="#">第1集 00:00</a></li>', '<li>开场：三种模式 <a class="src" href="#">第1集 00:00</a></li>'),
         ('蒸馏自 <N> 集共 <总分钟> 分钟，覆盖率 <NN>%', '蒸馏自 1 集共约 2 分钟，覆盖率 100%')]
for a, b in pairs:
    assert a in d, '模板缺少: ' + a
    d = d.replace(a, b)
open(os.path.join(series, 'draft.html'), 'w', encoding='utf-8').write(d)
print('draft.html 已从模板生成')
