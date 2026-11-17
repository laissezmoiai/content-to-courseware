# content-to-courseware

把视频链接/视频文件、PDF/Word/PPT 文档、电子书或长文章蒸馏成带出处的知识卡，再编排成可快速阅读学习的可视化课件（单文件 HTML，可导出 PDF）。

## 依赖

Python 3.10+；`pip install faster-whisper`；系统 `ffmpeg`（含 ffprobe）、`yt-dlp`；`gsk` CLI（转写辅助、画面识别、截图自检走它）——盲测环境必须有 gsk，装环境耗时单独记，不算流程耗时。

## 安装

把 `SKILL.md`、`scripts/`、`templates/`、`references/` 一起复制进你的 Agent 技能目录即可。

## 一键回归

```bash
./run_tests.sh
```

在全新克隆里可直接跑：自动恢复测试初始态（清锁清卡，freeze 后才写卡）→ 冻结 → 卡片验收 → 帧核对 → 覆盖率验收（输出「覆盖率：」行）→ 渲染 → 出片自检 → 3 个反例（摘录非逐字 / 数字无据 / 演示段缺帧）→ 改稿降级实测。任何一步失败即非零退出。

## 目录

- `SKILL.md` — 技能主文件（流程、格式、纪律）
- `scripts/` — 10 个脚本（共用模块、取材、转写、五个检查器、渲染、熔断）；`run_tests.sh` 在根目录，`testdata/gen_draft.py` 是回归专用草稿生成器
- `templates/courseware.html` — 课件骨架（与渲染、自检脚本配套；勿手写卡片，用 `<!--CARD 编号-->` 占位）
- `templates/library/` — registry / 主题树 / 术语表 / merge-log / conflicts 空表
- `references/design-spec.md` — 视觉规范
- `testdata/` — 最小测试数据（1 集 / 4 卡 / 1 帧）

四条已知问题（盲测前已知，撞上不算新问题）：
1. check_frames 对「路径」字段保留校正稿回退（警告级）——路线图 P5
2. 冻结指纹暂不含段落性质与依据帧——P5
3. 只有本地文件、登记表无来源链接的素材，渲染会报错「登记表里找不到系列 X 的来源链接」（定位点解析得出来、链接拼不出来时的准确报错；定位点本身解析失败才报「定位点读不出来」）——P3 顺手加「本地文件」分支
4. `ingest_media.sh` 是单视频路径：帧输出序号命名、文本不在 `sources/`、无校正稿生成，与检查器不匹配——多集走 asr.py 路线，单视频盲测前先用手工命令补齐
5. asr.py 续跑逻辑复用 `subs/` 旧分段，会产生「假重转写」（新 raw.md 与旧稿 md5 相同）——重跑/换模型/换提示词前必须先清 `sources/subs/*.md`（wb-adv 盲测实测）
6. faster-whisper 的 `initial_prompt` 只作用于第一个 30 秒窗口，术语 hotwords 必须走 `hotwords` 参数（2026-11-17 起 asr.py 已改，beam_size 同步升到 5）；沙箱 4GB 跑不动 large-v3/medium（OOM exit 137），沙箱内用 large-v3-turbo，完整 Large-V3 走用户本机 MLX + 双稿比对（SKILL.md 阶段 0）
7. 帧识别（gsk understand_images）返回的是转述型描述，不是逐字抄录——版本号等「看似精确」的转述（实测出现过 `WorkBuddy v1.x.x`，画面上不可能有）不可当画面真值；识别指令必须写明逐字抄录、〔?〕占位、不许概括
