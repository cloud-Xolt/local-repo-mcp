# Local Repo MCP 1.2.2

这是一个只面向一个本地用户、一个 Git 仓库的轻量安全 MCP。

## 本次完整修复

- Windows 下统一 Diff 标准化为 LF，并以 UTF-8 bytes 直接传给
  `git apply`，不再经过会转换换行的文本管道。
- 脏工作区检查改为只检查 Patch 目标文件；无关未跟踪文件不再阻塞
  所有修改。
- 预定义测试会丢弃未展开的 `%VAR%`，使用仓库外临时目录，并关闭
  pytest 缓存。
- Streamable HTTP 无论是否只监听本机，都强制 Bearer Token。
- 审计增加事件、进程、传输、模式和仓库元数据。
- MCP Tool 返回实际仓库根路径，GUI 连接测试会核对是否连错仓库。
- 桌面端现已统一为一套原生设计系统，不再通过运行期补丁覆盖控件：采用
  暖中性色、232 px 导航、统一 44 px 控件、15 px 正文基线与 3:2 表单网格，
  并同步适配浅色与深色主题。
- `sitecustomize.py` 已废弃，必须删除。

## 桌面界面

使用 `python run_gui.py` 启动（Windows 也可运行 `start_gui.bat`）。界面会持续
显示当前仓库与权限模式，将低频设置折叠，并明确区分服务、ChatGPT Tunnel
和日志流程。所有视觉令牌集中在 `gui/theme.py`；`gui/ui_overrides.py` 只保留为
旧启动器兼容入口，不再修改运行中的控件树。

## 手工替换

停止 GUI 和 `tunnel-client`，将 `replacement/` 下的所有文件按原路径
复制到仓库根目录并覆盖。

从压缩包目录执行一次：

```powershell
.\cleanup_legacy_residue.ps1
```

该脚本只删除此前失败更新产生的以下残留：

```text
sitecustomize.py
conftest.py
%SystemDrive%/
.pytest_cache/local_repo_update/
```

然后测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

## 安全边界

本项目是单用户本地工具，不提供任意 Shell、无限制写入、自动 Commit、
Git push/reset/rebase/checkout、多用户 RBAC 或不可信代码沙箱。

推荐使用 STDIO Tunnel。Runtime API Key 用于 `tunnel-client` 向 OpenAI
控制面认证；ChatGPT 显示“无认证”表示没有第二层 MCP OAuth，不表示公网
匿名开放。

Streamable HTTP 必须配置：

```text
HTTP_AUTH_MODE=bearer
HTTP_AUTH_TOKEN=<随机 Token>
```
