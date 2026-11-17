# content-to-courseware

把视频链接/视频文件、PDF/Word/PPT 文档、电子书或长文章蒸馏成带出处的知识卡，再编排成可快速阅读学习的可视化课件（单文件 HTML，可导出 PDF）。

## 安装

把 `SKILL.md`、`scripts/`、`templates/`、`references/` 一起复制进你的 Agent 技能目录即可。

## 一键回归

```bash
./run_tests.sh
```

在全新克隆里可直接跑：自动恢复测试初始态（清锁清卡，freeze 后才写卡）→ 冻结 → 卡片验收 → 帧核对 → 覆盖率验收（输出「覆盖率：」行）→ 渲染 → 出片自检 → 3 个反例（摘录非逐字 / 数字无据 / 演示段缺帧）→ 改稿降级实测。任何一步失败即非零退出。

## 目录

- `SKILL.md` — 技能主文件（流程、格式、纪律）
- `scripts/` — 8 个脚本（取材、转写、五个检查器、渲染、熔断），另有 `run_tests.sh` 一键回归在根目录
- `templates/courseware.html` — 课件骨架（与渲染、自检脚本配套；勿手写卡片，用 `<!--CARD 编号-->` 占位）
- `templates/library/` — registry / 主题树 / 术语表 / merge-log / conflicts 空表
- `references/design-spec.md` — 视觉规范
- `testdata/` — 最小测试数据（1 集 / 4 卡 / 1 帧）

两条外部审稿后的已知残留（路线图 P5）：check_frames 对「路径」字段保留校正稿回退（警告级）；冻结指纹暂不含段落性质与依据帧。
