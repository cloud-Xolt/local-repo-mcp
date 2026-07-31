# Local Repo MCP — AI Agent 开发约束

**修改任何代码前，必须先阅读 [CONTRIBUTING.md](./CONTRIBUTING.md)。**

## 代码生成前检查清单

1. 阅读 `CONTRIBUTING.md` 与 `.cursor/rules/security-runtime.mdc`
2. 不绕过：Policy、RBAC、Risk Scorer、Session、Branch Sandbox、Secret Scanner、Audit、Docker Sandbox
3. 新 Tool 必须：Schema、权限、风险等级、Policy Check、RBAC Check、Audit Event、测试
4. 写：`repo_prepare_patch` → `repo_approve_patch` → `repo_apply_patch`
5. 测：`repo_run_test(command_key)` + Sandbox
6. Patch 目标仅 `git apply --stat`；写入仅在 `agent/{session_id}` 分支

## 关键模块

| 模块 | 路径 |
|------|------|
| 入口 | `server.py` → `src/mcp_app/server.py` |
| Tools | `src/tools/read.py`, `patch.py`, `test.py`, `session.py` |
| Policy | `src/security/policy_engine.py`, `config/policy.yaml` |
| RBAC | `src/security/rbac.py` |
| Risk | `src/security/risk.py` |
| 测试 | `tests/test_*.py` |

## 验证

```bash
python -m pytest tests/ -v
python server.py
```
