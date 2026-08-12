# Local Repo MCP — AI 开发约束

本项目是**轻量、单一用途**的本地 Git 仓库 MCP Server，不是企业 Agent Runtime。

## 第一约束：工具定位

本项目只提供单仓库的受控远程开发、测试/构建执行和结果回传能力。设计必须保持轻量、固定工具面、受控执行和结果可核验；禁止演进为 Agent、任务编排平台或通用远程 Shell。

## 产品边界

- 只服务**一个**配置的本地 Git 仓库
- 默认 `MCP_MODE=read`
- 仅支持 `read` / `write` / `test` 三档模式
- 写入主要通过 `repo_apply_patch`（统一文本 Patch）
- 可选 `repo_git_commit`（默认关闭；GUI/`ALLOW_GIT_COMMIT` 显式开启后，write/test 可创建本地 commit）
- 可选 `repo_run_test`（仅 test 模式，白名单 test/build/lint/check；兼容单命令与有界顺序批量）
- 可选 OpenAI Secure MCP Tunnel（用户自行安装 tunnel-client）

## 禁止新增

- Session / RBAC / Risk Scorer / Policy YAML
- 自动分支 checkout / push / amend / reset / rebase
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
6. 保持 MCP Tool 数量为 8 个，不随意新增
7. 所有 MCP Tool 必须发布稳定的 `inputSchema` 与 `outputSchema`；可选参数通过 default/required 表达，避免不必要的 nullable union
8. 协议契约统一定义在 `src/tools/contracts.py`，并由真实 `tools/list` 回归测试验证，禁止为单个客户端写 Tool 特判

## MCP Tools（仅这 8 个）

```
repo_list_files
repo_read_file
repo_search_code
repo_git_status
repo_git_diff
repo_apply_patch
repo_git_commit
repo_run_test
```

## 核心模块

```
src/security/guard.py    — 路径 denylist
src/security/scanner.py  — Patch 新增行凭证 regex
src/repo/filesystem.py   — 读取与列表
src/repo/git.py          — 过滤后的 Git 操作
src/tools/contracts.py   — 统一 MCP Tool 协议契约与 tools/list schema 自检
src/tools/patches.py     — 原子统一 Patch 适配层（支持一次修改多个文件）
src/commands/models.py   — CommandSpec / CommandResult / BatchResult
src/commands/registry.py — 固定白名单命令注册
src/commands/runner.py   — 统一受控命令执行核心
src/tools/test_runner.py — 旧 Python 入口兼容层，不承载生产执行逻辑
launch_mcp.py            — Tunnel 固定 launcher
```
