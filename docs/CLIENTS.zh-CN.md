# ChatGPT 与其他 MCP 客户端

[简体中文](CLIENTS.zh-CN.md) | [English](CLIENTS.md)

Local Repo MCP 可以用于支持 ChatGPT 构建和维护本地项目，但它不是 ChatGPT 专用集成。它本质上是一个面向单个本地 Git 工作区的通用 MCP Server。

任何兼容 MCP 的客户端、编码 Agent、IDE、桌面应用或自动化平台，都可以通过 STDIO 或 Streamable HTTP 使用相同的工具。

## 使用 ChatGPT 构建本地项目

Local Repo MCP 要求所选目录是 Git 工作区。新建项目时，先创建空目录，在 GUI 中选择该目录，并明确确认 Git 初始化提示。

然后执行以下步骤：

1. 启动 Local Repo MCP GUI。
2. 选择刚创建的 Git 工作区。
3. ChatGPT 只需要创建和修改项目文件时，选择 `write` 模式。
4. ChatGPT 还需要运行白名单 test/build/lint/check 命令时，选择 `test` 模式。
5. 选择连接方式。
6. 连接 ChatGPT，并描述需要生成的项目结构、源代码、配置、文档和测试。

在所选权限模式内，ChatGPT 可以：

- 检查仓库目录结构；
- 读取允许访问的 UTF-8 文本文件；
- 检索代码；
- 通过经过校验的统一 Patch 原子创建和修改一个或多个文件；
- 查看经过过滤的 Git 状态和 Diff；
- 在 `test` 模式运行单个或有界顺序批量的白名单验证命令，并获得可核验执行结果。

Local Repo MCP 不开放无限制 Shell，也不允许任意 checkout、reset、rebase、merge、pull、push 或 amend。本地 commit 默认关闭，需显式开启。

## 接入 ChatGPT

面向 ChatGPT 的部署可以选择：

- **OpenAI Secure MCP Tunnel**：使用 GUI 管理的 STDIO Tunnel 流程；
- **Streamable HTTP**：由集成连接本地或远程 MCP 端点。

Secure MCP Tunnel 页面负责管理 Tunnel Profile、仅保存在进程内存中的 Runtime API Key、Doctor 检查和 Tunnel 进程生命周期。

使用 Streamable HTTP 时始终需要 Bearer 认证。远程部署必须使用原生 TLS/mTLS，或者显式配置可信的 TLS 终止反向代理。

## 接入其他 MCP 客户端

其他兼容 MCP 的客户端使用同一个服务端实现和相同的 8 个 MCP 工具。

### STDIO

当客户端可以把 Local Repo MCP 作为子进程启动时，使用 STDIO。将 **MCP Server** 页面生成的客户端配置复制到对应客户端。

STDIO 适用于：

- 本地编码 Agent；
- 支持 MCP 的 IDE；
- 桌面 MCP 客户端；
- 本地自动化进程。

### Streamable HTTP

当客户端需要连接常驻 MCP 端点时，使用 Streamable HTTP。

客户端需要支持：

- 配置的 MCP 端点路径；
- Bearer 认证；
- Streamable HTTP；
- HTTPS 部署中的 TLS 证书验证；
- 启用 mTLS 时使用客户端证书。

不同兼容客户端可以使用同一个端点，但 Local Repo MCP 仍然是面向单用户、单仓库的工具，不是多租户授权服务。

## 所有客户端使用相同工具和控制

客户端身份不会改变服务端能力。ChatGPT 与其他 MCP 客户端获得相同的工具：

| 工具 | 能力 |
| --- | --- |
| `repo_list_files` | 列出允许访问的仓库文件。 |
| `repo_read_file` | 读取允许访问的 UTF-8 文本文件。 |
| `repo_search_code` | 执行有边界的固定字符串检索。 |
| `repo_git_status` | 读取经过过滤的 Git 状态。 |
| `repo_git_diff` | 读取受大小限制并经过过滤的 Git Diff。 |
| `repo_apply_patch` | 原子应用统一文本 Patch，可一次修改多个文件。 |
| `repo_git_commit` | 显式开启后，为允许的改动创建一次本地 commit。 |
| `repo_run_test` | 在 `test` 模式运行单个或有界批量的白名单验证命令，并返回退出码与 stdout/stderr。 |

所有客户端都受到相同的以下控制：

- 配置的仓库根目录；
- 权限模式；
- 路径穿越、符号链接、硬链接和敏感路径限制；
- 输入、输出、检索、文件、Patch 和测试限制；
- Patch 校验和目标文件已有修改保护；

## 目录选择与 Git 初始化

手工执行 `git init` 不是必需步骤。用户选择普通目录时，GUI 会立即检查，并在初始化前要求用户明确确认；手工输入路径时，点击“连接”或“启动”前还会再次检查。

取消确认后目录保持不变。初始化只创建本地 `.git` 元数据，Local Repo MCP 不会创建 Commit、配置远程仓库或发布项目。若所选子目录已经位于现有 Git 工作区中，该子目录不能作为独立安全边界；GUI 会提示切换到实际的 Git 工作区根目录。

目标机器仍然需要安装 Git 并可通过 `PATH` 找到，因为仓库状态、Diff、Patch 校验和写入锁都依赖 Git。
