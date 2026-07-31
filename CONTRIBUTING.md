# Local Repo MCP 轻量化安全整改

## 定位

轻量、单一用途的本地 Git 仓库 MCP Server — 非企业 Agent Runtime。

## 实现状态

| 模块 | 状态 | 位置 |
|------|------|------|
| 路径 guard | ✅ | `src/security/guard.py` |
| 凭证 regex | ✅ | `src/security/scanner.py` |
| 安全读取/列表 | ✅ | `src/repo/filesystem.py` |
| 过滤 Git | ✅ | `src/repo/git.py` |
| 单步 Patch | ✅ | `src/tools/patch.py` |
| 白名单测试 | ✅ | `src/tools/test_runner.py` |
| 固定 launcher | ✅ | `launch_mcp.py` |
| 轻量 GUI | ✅ | `gui/app.py`（4 页） |

## MCP Tools（7 个）

`repo_list_files`, `repo_read_file`, `repo_search_code`, `repo_git_status`, `repo_git_diff`, `repo_apply_patch`, `repo_run_test`

## 已删除

Session, RBAC, Risk, Policy YAML, Agent 分支, Patch 审批, Docker Sandbox, Tunnel 自动安装, 本地组件注册

## 开发约束

见 `AGENTS.md` 与 `local-repo-mcp-lightweight-security-refactor-guide.md`
