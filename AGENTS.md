# Local Repo MCP — AI 开发约束

本项目是**轻量、单一用途**的本地 Git 仓库 MCP Server，不是企业 Agent Runtime。

## 产品边界

- 只服务**一个**配置的本地 Git 仓库
- 默认 `MCP_MODE=read`
- 仅支持 `read` / `write` / `test` 三档模式
- 写入仅通过 `repo_apply_patch`（统一文本 Patch）
- 可选 `repo_run_test`（仅 test 模式，白名单命令）
- 可选 OpenAI Secure MCP Tunnel（用户自行安装 tunnel-client）

## 禁止新增

- Session / RBAC / Risk Scorer / Policy YAML
- 自动分支 checkout / commit / push
- 三阶段 Patch 审批
- Docker Sandbox / 任意 Shell
- Tunnel 自动下载
- API Key 落盘

## 每次修改必须

1. 路径使用 `relative_to()`，拒绝绝对路径、`..`、symlink
2. 敏感路径使用 `src/security/guard.py` denylist
3. Git status/diff 过滤敏感路径
4. 搜索使用 `rg --fixed-strings -e query --`
5. 同步更新 `tests/` 与 README
6. 保持 MCP Tool 数量为 7 个，不随意新增

## MCP Tools（仅这 7 个）

```
repo_list_files
repo_read_file
repo_search_code
repo_git_status
repo_git_diff
repo_apply_patch
repo_run_test
```

## 核心模块

```
src/security/guard.py    — 路径 denylist
src/security/scanner.py  — Patch 新增行凭证 regex
src/repo/filesystem.py   — 读取与列表
src/repo/git.py          — 过滤后的 Git 操作
src/tools/patch.py       — 单步 Patch
src/tools/test_runner.py — 白名单本地测试
launch_mcp.py            — Tunnel 固定 launcher
```
