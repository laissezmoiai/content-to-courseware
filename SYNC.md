# 副本同步纪律（2026-11-17 事故后定死）

**仓库是唯一来源（single source of truth）。** `~/.opencode/skills/content-to-courseware/` 只是仓库的单向镜像。

- 改动一律在 `/tmp/opencode/repo`（仓库克隆）里做、提交、push。
- 技能库只从仓库**单向同步**，禁止任何方向的反向 `cp`：
  `rsync -a --delete --exclude '*.pyc' --exclude '__pycache__' --exclude 'testdata/' /tmp/opencode/repo/ ~/.opencode/skills/content-to-courseware/`（testdata 按需另拷）
- 同步后必须做一次 `diff -r` 比对，输出为空才算同步成功。
- 事故记录：`fc0f1b1` 曾因反向 cp 把旧模板盖回仓库，回归脚本（exit=1）当场抓住。
