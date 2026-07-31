# Local Repo MCP

将本地 Git 代码仓库以**最小权限**方式接入 ChatGPT，配合 [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) 使用，无需把 MCP Server 暴露到公网。

```text
ChatGPT → Custom MCP App → Secure MCP Tunnel → tunnel-client → Local Repo MCP → 本地仓库
```

## 特性

- **路径沙箱**：所有操作限制在 `REPO_ROOT` 内
- **Denylist**：拒绝读取 `.env`、私钥、凭证等敏感路径
- **权限分层**：`read` / `write` / `test` 三阶段开放
- **受控写入**：仅支持 `apply_patch`，含密钥扫描与 worktree 检查
- **测试白名单**：通过 `command_key` 枚举运行测试，禁止任意 Shell
- **审计日志**：所有工具调用写入 `AUDIT_LOG`
- **GUI 控制面板**：一键配置、启动与监控

## 项目结构

```text
local-repo-mcp/
├── server.py              # MCP Server 核心
├── gui/                   # GUI 控制面板
├── run_gui.py
├── start_gui.bat          # Windows 一键启动 GUI
├── requirements.txt
├── .env.example
├── systemd/               # Linux 部署示例
└── README.md
```

## 环境要求

- Python 3.11+
- Git 2.39+
- ripgrep（`rg`，用于代码搜索）
- [tunnel-client](https://github.com/openai/tunnel-client)（接入 ChatGPT 时需要）

## 快速开始

### 1. 安装依赖

```bash
git clone git@github.com:cloud-Xolt/local-repo-mcp.git
cd local-repo-mcp
python -m venv .venv

# Windows
.venv\Scripts\activate
.venv\Scripts\pip install -r requirements.txt

# Linux / macOS
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 使用 GUI（推荐）

**Windows：** 双击 `start_gui.bat`

```bash
python run_gui.py
```

在界面中填写：

| 配置项 | 说明 |
|--------|------|
| 仓库路径 | 本地 Git 仓库根目录 |
| 运行模式 | 建议从 `read` 开始 |
| Tunnel ID | OpenAI Platform 创建的 tunnel |
| API Key | Control Plane API Key |

点击 **保存配置** → **一键启动全部** 即可。

### 3. 命令行启动 MCP Server

```bash
export REPO_ROOT=/path/to/your/repo
export MCP_MODE=read
export AUDIT_LOG=./audit.log

python server.py
```

## 接入 ChatGPT

### 前置条件

1. ChatGPT 工作区已开启 Developer Mode
2. OpenAI Platform 已创建 Tunnel 并关联到目标工作区
3. 已安装 `tunnel-client`

### 初始化 Tunnel

```bash
export CONTROL_PLANE_API_KEY="sk-..."

tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile local-repo \
  --tunnel-id tunnel_xxxxxxxx \
  --mcp-command "bash -lc 'cd /opt/local-repo-mcp && source .venv/bin/activate && REPO_ROOT=/opt/repos/project-a MCP_MODE=read python server.py'"

tunnel-client doctor --profile local-repo --explain
tunnel-client run --profile local-repo
```

### 创建 Custom MCP App

在 ChatGPT 中：**Apps → Create developer-mode app → Connection 选择 Tunnel → Scan Tools → Create**

## MCP 工具

| 工具 | 模式 | 说明 |
|------|------|------|
| `repo_list_files` | read | 列出仓库文件 |
| `repo_read_file` | read | 读取指定文件 |
| `repo_search_code` | read | ripgrep 搜索代码 |
| `repo_git_status` | read | 查看 git status |
| `repo_git_diff` | read | 查看 git diff |
| `repo_apply_patch` | write | 应用 unified diff patch |
| `repo_run_test` | test | 运行白名单测试命令 |

### 测试命令白名单

| command_key | 命令 |
|-------------|------|
| `python_pytest` | `pytest -q` |
| `go_test` | `go test ./...` |
| `node_test` | `npm test` |
| `node_lint` | `npm run lint` |
| `maven_test` | `mvn test` |
| `gradle_test` | `./gradlew test` |

## 配置说明

复制 `.env.example` 为 `.env`，或通过 GUI 保存到 `config.json`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `REPO_ROOT` | `.` | 仓库根目录 |
| `MCP_MODE` | `read` | 运行模式：`read` / `write` / `test` / `ship` |
| `MAX_FILE_BYTES` | `200000` | 单文件最大读取字节 |
| `MAX_PATCH_BYTES` | `200000` | Patch 最大字节 |
| `ALLOW_DIRTY_WORKTREE` | `false` | 是否允许 dirty 时 apply patch |
| `AUDIT_LOG` | `./audit.log` | 审计日志路径 |

## 推荐上线阶段

1. **阶段一** — `MCP_MODE=read`：只读查看代码与 Git 状态
2. **阶段二** — `MCP_MODE=write`：开放 `repo_apply_patch`
3. **阶段三** — `MCP_MODE=test`：开放 `repo_run_test`

**永不开放：** 任意 Shell、`git push`、`git reset`、`git rebase` 等危险操作。

## Linux 部署

参考 `systemd/` 目录下的 service 文件，以低权限用户 `repo-mcp` 运行。

## 安全提示

- 不要将 `config.json`、`.env`、`CONTROL_PLANE_API_KEY` 提交到 Git
- 默认使用 `read` 模式，验证通过后再逐步开放写入
- `git push` 建议手动完成，不交给 ChatGPT

## 参考资料

- [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [tunnel-client](https://github.com/openai/tunnel-client)
- [ChatGPT Developer Mode](https://help.openai.com/en/articles/12584461-developer-mode-apps-and-full-mcp-connectors-in-chatgpt-beta)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## License

MIT
