# Local Repo MCP 安全增强开发指导文档

## 目标

将 local-repo-mcp 升级为 **Secure Agent Coding Runtime**。

---

## 实现状态（全部完成）

| 模块 | 状态 | 实现位置 |
|------|------|----------|
| Policy Engine | ✅ | `src/security/policy_engine.py`, `config/policy.yaml` |
| Enterprise RBAC | ✅ | `src/security/rbac.py` |
| Risk Scoring | ✅ | `src/security/risk.py` |
| Session Manager | ✅ | `src/session/manager.py` |
| Git Branch Sandbox | ✅ | `src/repo/branch.py` |
| Patch 校验 | ✅ | `src/tools/patch.py`, `src/repo/patch.py` |
| Secret Scanner | ✅ | `src/security/scanner.py` |
| Prompt Injection 防护 | ✅ | `src/security/trust_boundary.py` |
| Audit Framework | ✅ | `src/audit/logger.py` |
| Test Sandbox | ✅ | `src/sandbox/executor.py` |
| Approval Workflow | ✅ | prepare → approve → apply |
| 目录拆分 | ✅ | `src/tools/`, `src/mcp_app/`, `config/` |
| 安全测试 | ✅ | `tests/test_*.py` |

---

## 目录结构

```
local-repo-mcp/
├── server.py                 # 入口 shim
├── config/policy.yaml        # 策略 + RBAC + 风险阈值
├── src/
│   ├── mcp_app/server.py     # MCP 注册与启动
│   ├── tools/                # read / patch / test / session
│   ├── security/             # policy_engine, rbac, risk, scanner
│   ├── session/
│   ├── repo/
│   ├── sandbox/
│   └── audit/
├── tests/                    # 安全验收测试
├── gui/
├── AGENTS.md
└── .cursor/rules/security-runtime.mdc
```

---

## Tool 规范

### Write 流程

`repo_prepare_patch` → `repo_approve_patch` → `repo_apply_patch`

### Execute

仅 `repo_run_test(command_key)`，经 Docker Sandbox。

### RBAC

Session 启动时校验 `config/policy.yaml` 中 `rbac.users` 与 `rbac.roles`。

### Risk Scoring

高风险操作（score ≥ block_threshold）自动拒绝；审计记录 `risk_score`。

---

## AI 开发约束

修改代码前必读本文档与 `AGENTS.md`；Cursor 通过 `.cursor/rules/security-runtime.mdc` 自动加载。

### 禁止

- 任意 shell、`shell=True`、绕过 Policy/Sandbox/RBAC/Risk
- `write_file`、`run_command(任意字符串)`、自动 git push

### 必须

新 Tool：Schema + 权限 + 风险等级 + Policy + RBAC + Audit + 测试

---

## 安全验收

运行：`python -m pytest tests/ -v`

覆盖：路径逃逸、.env/.ssh/.git、protected 分支、Secret 阻断、RBAC、Risk Scoring。
