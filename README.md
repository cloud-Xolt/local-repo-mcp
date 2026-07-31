# Local Repo MCP

<p align="right">
  <strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <strong>Safely connect one local Git repository to ChatGPT and other MCP clients.</strong>
</p>

<p align="center">
  Read, search, inspect Git changes, apply validated patches, and optionally run trusted tests—without exposing a general-purpose shell or your entire filesystem.
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="MCP Server" src="https://img.shields.io/badge/MCP-Server-6C47FF">
  <img alt="Default mode" src="https://img.shields.io/badge/default-read--only-2EA44F">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-blue">
</p>

---

## What is Local Repo MCP?

Local Repo MCP is a small, security-focused MCP server for one local Git repository.

It gives ChatGPT and other MCP clients enough access to understand and modify a repository, while deliberately avoiding broad operating-system access.

It supports:

- listing repository files;
- reading UTF-8 source files;
- searching source code;
- inspecting filtered Git status and diff;
- applying validated text patches;
- optionally running predefined tests for repositories you trust;
- optionally connecting to ChatGPT through OpenAI Secure MCP Tunnel.

It does **not** expose:

- a general-purpose shell;
- unrestricted filesystem access;
- arbitrary file writes;
- `git push`, `pull`, `checkout`, `reset`, `rebase`, or `merge`.

---

## Why use it?

AI coding tools need access to source code, but broad filesystem or terminal access may be more permission than you want to provide.

Local Repo MCP follows a smaller permission model:

```text
One local Git repository
        +
Read-only by default
        +
No general-purpose shell
        +
Patch-only code changes
        +
No automatic Git publishing
```

The project intentionally stays small. It is not an enterprise agent platform, policy engine, multi-user gateway, or cloud coding service.

---

## Key Features

### One repository only

All file and Git operations are confined to one configured repository root.

The server rejects:

- absolute paths;
- parent traversal such as `../`;
- symbolic links;
- paths outside the configured repository;
- common sensitive files such as `.env`, private keys, credentials, and `.git` internals.

### Read-only by default

The default `read` mode exposes inspection tools only. Write and test capabilities must be explicitly enabled.

### Patch-only writes

The server does not expose unrestricted `write_file`.

```text
Validate patch size
        ↓
Resolve affected paths
        ↓
Block sensitive targets
        ↓
Detect common credential patterns
        ↓
Run git apply --check
        ↓
Apply the patch
        ↓
Return a filtered Git diff
```

### No general-purpose shell

There is no `run_shell`, `run_command`, or equivalent tool. Optional test execution accepts predefined command keys only.

### Optional bilingual GUI

The GUI supports English and Simplified Chinese and provides:

- repository selection;
- access-mode selection;
- MCP start and stop controls;
- optional Secure MCP Tunnel settings;
- connection diagnostics;
- live logs;
- collapsible advanced settings.

### Optional ChatGPT connection

Local MCP clients can launch the server directly through stdio. ChatGPT can optionally reach the local MCP server through OpenAI Secure MCP Tunnel without publishing the server to the public internet.

---

## Architecture

### Local MCP client

```text
Cursor / Claude Desktop / another MCP client
                     │
                     │ stdio
                     ▼
              Local Repo MCP
                     │
                     ▼
              Local Git Repo
```

### ChatGPT through Secure MCP Tunnel

```text
ChatGPT
   │
Custom MCP App
   │
OpenAI Secure MCP Tunnel
   │
tunnel-client
   │
Local Repo MCP
   │
Local Git Repo
```

Secure MCP Tunnel is optional.

---

## Access Modes

| Mode | Display name | Capabilities |
|---|---|---|
| `read` | Read Only | List, read, search, Git status, Git diff |
| `write` | Read & Write | Read tools plus validated patch application |
| `test` | Read, Write & Test | Write tools plus predefined test commands |

Start with `read` and enable additional capabilities only when required.

---

## MCP Tools

| Tool | Minimum mode | Description |
|---|---|---|
| `repo_list_files` | `read` | List allowed repository files |
| `repo_read_file` | `read` | Read one allowed UTF-8 text file |
| `repo_search_code` | `read` | Search repository text with bounded results |
| `repo_git_status` | `read` | Return filtered Git working-tree status |
| `repo_git_diff` | `read` | Return filtered staged or unstaged Git diff |
| `repo_apply_patch` | `write` | Validate and apply a unified text patch |
| `repo_run_test` | `test` | Run one predefined test command |

The server intentionally does not expose arbitrary shell commands, arbitrary file writes, or dangerous Git operations.

---

## Requirements

| Dependency | Purpose |
|---|---|
| Python 3.11+ | MCP server and GUI |
| Git 2.39+ | Repository inspection and patch application |
| ripgrep (`rg`) | Fast source-code search |
| OpenAI `tunnel-client` | Optional ChatGPT connection |

Docker is not required.

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/cloud-Xolt/local-repo-mcp.git
cd local-repo-mcp
```

### 2. Create a virtual environment

#### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

#### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## Use the GUI

The GUI is the recommended setup method.

### Windows

```powershell
python run_gui.py
```

### Linux / macOS

```bash
python run_gui.py
```

### First-run flow

1. Choose a local Git repository.
2. Select an access mode.
3. Save the configuration.
4. Start the MCP server.
5. Connect your MCP client.

For ChatGPT, configure the optional Tunnel section after the local MCP server works correctly.

---

## GUI Layout

### Overview

Displays MCP status, Tunnel status, current repository, active mode, quick actions, and recent messages.

### MCP Configuration

Contains repository path, access mode, save, start, stop, and local connection test.

### Tunnel

Contains `tunnel-client` path, Tunnel ID, profile, temporary runtime API key, initialize, doctor, start, and stop.

The runtime API key must not be persisted to `config.json`.

### Logs

Displays MCP logs, Tunnel logs, audit events, and diagnostics.

### Advanced Settings

Collapsed by default:

- maximum file size;
- maximum patch size;
- maximum search results;
- maximum output size;
- dirty-worktree policy;
- audit-log path;
- test timeout.

The entire UI switches between English and Simplified Chinese. Do not permanently show both languages inside every field.

---

## Run from the Command Line

### Linux / macOS

```bash
export REPO_ROOT="/absolute/path/to/your/repository"
export MCP_MODE="read"
export AUDIT_LOG=""
python server.py
```

### Windows PowerShell

```powershell
$env:REPO_ROOT = "C:\absolute\path\to\your\repository"
$env:MCP_MODE = "read"
$env:AUDIT_LOG = ""
python server.py
```

The server communicates over stdio.

---

## Configure a Local MCP Client

```json
{
  "mcpServers": {
    "local-repo": {
      "command": "/absolute/path/to/local-repo-mcp/.venv/bin/python",
      "args": [
        "/absolute/path/to/local-repo-mcp/server.py"
      ],
      "env": {
        "REPO_ROOT": "/absolute/path/to/your/repository",
        "MCP_MODE": "read",
        "MAX_FILE_BYTES": "200000",
        "MAX_PATCH_BYTES": "200000",
        "MAX_SEARCH_RESULTS": "50",
        "MAX_OUTPUT_BYTES": "20000",
        "ALLOW_DIRTY_WORKTREE": "false",
        "AUDIT_LOG": ""
      }
    }
  }
}
```

On Windows, use the Python executable from `.venv\Scripts\python.exe`.

---

## Connect to ChatGPT

ChatGPT integration is optional.

Local Repo MCP remains on the local machine. OpenAI Secure MCP Tunnel provides the private connection path.

### Prerequisites

You need:

1. access to ChatGPT Developer Mode;
2. an OpenAI Platform Tunnel ID;
3. a runtime API key for `tunnel-client`;
4. the official OpenAI `tunnel-client`;
5. a working local Local Repo MCP installation.

### Initialize a stdio profile

```bash
export CONTROL_PLANE_API_KEY="sk-..."

tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile local-repo \
  --tunnel-id tunnel_0123456789abcdef0123456789abcdef \
  --mcp-command "/absolute/path/to/local-repo-mcp/.venv/bin/python /absolute/path/to/local-repo-mcp/server.py"
```

Validate and run:

```bash
tunnel-client doctor --profile local-repo --explain
tunnel-client run --profile local-repo
```

Local Repo MCP does not automatically download or update `tunnel-client`.

---

## Configuration

| Variable | Default | Description |
|---|---:|---|
| `REPO_ROOT` | `.` | Path of the single Git repository |
| `MCP_MODE` | `read` | `read`, `write`, or `test` |
| `MAX_FILE_BYTES` | `200000` | Maximum readable file size |
| `MAX_PATCH_BYTES` | `200000` | Maximum patch size |
| `MAX_SEARCH_RESULTS` | `50` | Maximum search result count |
| `MAX_OUTPUT_BYTES` | `20000` | Maximum diff or process output |
| `ALLOW_DIRTY_WORKTREE` | `false` | Allow patching an already modified worktree |
| `AUDIT_LOG` | empty | Optional audit-log path |
| `TEST_TIMEOUT_MAX` | `300` | Maximum test timeout in seconds |

Recommended first-use configuration:

```dotenv
REPO_ROOT=/absolute/path/to/repository
MCP_MODE=read
MAX_FILE_BYTES=200000
MAX_PATCH_BYTES=200000
MAX_SEARCH_RESULTS=50
MAX_OUTPUT_BYTES=20000
ALLOW_DIRTY_WORKTREE=false
AUDIT_LOG=
TEST_TIMEOUT_MAX=300
```

---

## Test Commands

Test execution is available only in `test` mode.

| `command_key` | Command |
|---|---|
| `python_pytest` | `python -m pytest -q` |
| `go_test` | `go test ./...` |
| `node_test` | `npm test --` |
| `node_lint` | `npm run lint --` |
| `maven_test` | `mvn test` |
| `gradle_test` | `./gradlew test` |

Users cannot provide arbitrary commands or additional command-line arguments.

> **Warning:** Test mode executes code from the configured repository. Enable it only for repositories you trust.

---

## Security Model

Local Repo MCP is designed for one local user, one configured Git repository, and one MCP server process.

The server:

- confines file access to `REPO_ROOT`;
- rejects absolute paths, parent traversal, and symbolic links;
- blocks common sensitive files;
- rejects binary and unsupported text files;
- limits file, patch, search, diff, and process-output sizes;
- filters blocked paths from Git status and diff;
- uses fixed subprocess arguments with `shell=False`;
- applies changes only through validated text patches;
- blocks several common credential patterns in added patch lines;
- never performs Git push, pull, checkout, reset, rebase, merge, stash, or clean;
- never exposes a general-purpose shell;
- does not persist the Tunnel runtime API key.

Typical blocked paths:

```text
.env
.env.*
.git/**
.ssh/**
*.pem
*.key
*.p12
*.pfx
id_rsa
id_ed25519
credentials/**
secrets/**
.github/workflows/**    # blocked for patch writes
```

Supported patch types:

```text
normal text-file additions
normal text-file modifications
normal text-file deletions
```

Rejected patch types:

```text
binary patches
symbolic-link creation
renames
copies
submodule changes
file-mode changes
```

### Limitations

- Credential-pattern detection is not a complete secret scanner.
- The MCP client controls user-facing confirmations.
- Write mode modifies the current working tree.
- Test mode executes repository code.
- Review `git diff` before committing.
- Perform commits and pushes manually.
- Use test mode only with trusted repositories.

---

## Audit Logging

Audit logging is optional. It may record timestamps, tool names, operation results, target paths, input sizes, and short hashes.

It must not record complete file contents, complete patches, search queries, API keys, tokens, passwords, or complete test output.

Leave `AUDIT_LOG` empty to disable it.

---

## Project Scope

### In scope

- one configured local Git repository;
- file listing and reading;
- bounded source-code search;
- filtered Git status and diff;
- validated text-patch writes;
- optional predefined test commands;
- optional GUI;
- optional Secure MCP Tunnel integration.

### Out of scope

- arbitrary shell access;
- general filesystem access;
- multi-user authentication;
- RBAC;
- enterprise policy engines;
- risk scoring;
- session orchestration;
- automatic branch management;
- automatic commit or push;
- cloud repository hosting;
- untrusted-code sandboxing;
- automatic `tunnel-client` installation.

Pull requests that significantly expand these boundaries may be declined.

---

## Troubleshooting

### `ripgrep` was not found

```bash
rg --version
```

### The selected path is not a Git repository

```bash
git -C /path/to/repository status
```

### A patch was rejected because the worktree is dirty

```bash
git status
git diff
```

Commit or stash manually, or carefully enable `ALLOW_DIRTY_WORKTREE=true`.

### The Tunnel is not visible in ChatGPT

Check the Tunnel ID, confirm `tunnel-client` is running, run `doctor`, verify workspace association, and verify account permissions.

---

## Development

```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -v
python -m compileall server.py src gui
```

Important security tests should cover path traversal, absolute paths, symlink escape, sensitive-file blocking, ripgrep option injection, Git diff filtering, unsupported patches, credential-pattern blocking, API-key persistence, command allowlisting, and `shell=False` enforcement.

---

## Roadmap

Planned:

- simplified packaging;
- PyPI distribution;
- Windows portable release;
- MCP Registry metadata;
- improved client setup guides;
- additional security tests;
- better GUI accessibility and localization;
- clearer diagnostics.

Not planned:

```text
RBAC
enterprise policy management
multi-user hosting
general shell access
automatic Git push
cloud execution platform
```

---

## Contributing

Contributions are welcome. Keep changes within the documented project scope, avoid expanding operating-system or Git permissions, add tests, and update both English and Chinese documentation for user-facing changes.

Good contribution areas include cross-platform compatibility, GUI usability, localization, security tests, packaging, documentation, error messages, and MCP client examples.

---

## License

Local Repo MCP is available under the MIT License.

---

## References

- OpenAI Secure MCP Tunnel  
  https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
- OpenAI `tunnel-client`  
  https://github.com/openai/tunnel-client
- ChatGPT Developer Mode and MCP Apps  
  https://help.openai.com/en/articles/12584461-developer-mode-apps-and-full-mcp-connectors-in-chatgpt-beta
- Model Context Protocol  
  https://modelcontextprotocol.io
- MCP Python SDK  
  https://github.com/modelcontextprotocol/python-sdk
