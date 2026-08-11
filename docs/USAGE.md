# Local Repo MCP Usage Guide

[English](USAGE.md) | [简体中文](USAGE.zh-CN.md)

This guide covers installation, initial configuration, STDIO, OpenAI Secure MCP Tunnel, Streamable HTTP, logs, tests, and common troubleshooting.

## 1. Prerequisites

Before starting, prepare:

- Python 3.11 or newer.
- Git available on `PATH`.
- One local Git working tree that Local Repo MCP is allowed to expose.
- `tunnel-client` only when using OpenAI Secure MCP Tunnel.

Verify the required commands:

```bash
python --version
git --version
```

The selected repository must pass:

```bash
git -C /path/to/repository rev-parse --is-inside-work-tree
```

## 2. Start from a source checkout

### Windows

Run from the repository root:

```powershell
start_gui.bat
```

### Linux/macOS

Run from the repository root:

```bash
chmod +x start_gui.sh
./start_gui.sh
```

The bootstrap process creates `.venv`, installs the required packages, and refreshes dependencies when `requirements.txt` changes.

## 3. Start after package installation

Install and launch the GUI:

```bash
pip install .
local-repo-mcp-gui
```

The MCP server entry point is:

```bash
local-repo-mcp
```

Source and installed layouts both use `mcp_app.launcher`.

## 4. First GUI configuration

Open the **Home** page and complete the following steps:

1. Select the target Git repository.
2. Select the permission mode.
3. Select the transport.
4. Review advanced limits when the defaults are not appropriate.
5. Start or connect according to the selected transport.

The GUI saves configuration automatically when an action needs it. A repository path is accepted only when it exists, is a directory, and is inside a Git working tree.

## 5. Choose a permission mode

### `read`

Use this mode for inspection only. It enables:

- file listing;
- UTF-8 text reads;
- fixed-string search;
- filtered Git status;
- filtered Git diff.

### `write`

Includes all read capabilities and enables `repo_apply_patch`.

Patch writes are limited to validated unified text patches. Sensitive paths, unsupported patch types, over-limit input, conflicting target changes, and likely credentials are rejected.

### `test`

Includes read and write capabilities and enables `repo_run_test`.

Test mode runs only registered test/build/lint/check commands. It supports one command or a bounded sequential batch of at most 8 commands, with the entire batch allowlist-validated before the first command starts. Repository code still executes with the current operating-system user's permissions; this is not a sandbox.

## 6. Use STDIO

STDIO is the recommended local transport when the MCP client can launch the server as a child process.

### Verify STDIO in the GUI

1. Select **STDIO** on the Home page.
2. Select the repository and mode.
3. Select **Connect**.
4. Wait for the real connection test to finish.

The test performs:

- MCP initialize;
- tool discovery;
- `repo_git_status` execution;
- configured repository identity verification.

STDIO is on demand. The GUI does not keep a permanent STDIO server process running after the connection test ends.

### Copy the client configuration

Open **MCP Server**, expand **Client configuration**, and copy the generated JSON into the MCP client that will launch Local Repo MCP.

The generated configuration contains:

- the current Python executable;
- the packaged launcher module;
- the configured repository root;
- the selected permission mode;
- input/output limits;
- runtime and audit log paths.

Restart or reload the MCP client after changing the configuration.

## 7. Use OpenAI Secure MCP Tunnel

Secure MCP Tunnel is optional. Install `tunnel-client` separately and obtain the Tunnel ID and Runtime API Key required by the control plane.

Automatic profile setup is intended for STDIO.

### Configure the Tunnel page

1. Keep Local Repo MCP transport set to **STDIO**.
2. Open **ChatGPT Connection**.
3. Set **Tunnel client** to `tunnel-client` or its full executable path.
4. Set a profile name, such as `local-repo`.
5. Enter the Tunnel ID.
6. Enter the Runtime API Key.
7. Optionally set an explicit profile path.

### Initialize and start

Run the actions in this order:

1. **Detect** — verifies the executable and existing profile.
2. **Initialize** — creates the STDIO Tunnel profile.
3. **Doctor** — validates the profile and runtime configuration.
4. **Start Tunnel** — starts `tunnel-client run --profile <profile>`.

The Runtime API Key remains in process memory and is not written to Local Repo MCP's normal configuration file.

When the source location or Python executable changes, **Detect** can repair a recognized Local Repo MCP command in the profile. A backup is created before changing the profile.

For a manually configured HTTP Tunnel, start the Streamable HTTP server first and ensure the Tunnel forwards the Bearer header. Automatic HTTP profile initialization is intentionally disabled.

## 8. Use local Streamable HTTP

Use Streamable HTTP when a client connects to a long-running endpoint instead of launching STDIO.

### Recommended local settings

```text
Host: 127.0.0.1
Port: 8000
Path: /mcp
Allowed hosts: 127.0.0.1:*,localhost:*
Allowed origins: http://127.0.0.1:*,http://localhost:*
```

### Start and verify

1. Select **Streamable HTTP**.
2. Keep the loopback host unless remote access is required.
3. Generate or enter the Bearer token.
4. Select **Start HTTP**.
5. Wait until the readiness check succeeds.
6. Select **Connect** to run MCP initialization and repository verification through HTTP.
7. Open **MCP Server** and copy the generated client configuration.

The client must send:

```text
Authorization: Bearer <LOCAL_REPO_MCP_TOKEN>
```

Bearer authentication is mandatory, including on loopback.

## 9. Use remote Streamable HTTP

Do not expose plaintext Local Repo MCP HTTP directly to an untrusted network.

Choose one of these models:

### Native TLS

Configure:

```text
HTTP_TLS_CERTFILE=/path/to/server.crt
HTTP_TLS_KEYFILE=/path/to/server.key
```

Optional mutual TLS:

```text
HTTP_TLS_CLIENT_CA=/path/to/client-ca.crt
```

### Trusted TLS reverse proxy

Configure:

```text
HTTP_TLS_TERMINATED_PROXY=true
HTTP_PUBLIC_URL=https://mcp.example.com/mcp
HTTP_PROXY_TRUSTED_IPS=10.0.0.0/8
```

The proxy must terminate HTTPS, preserve the MCP path and Authorization header, prevent direct untrusted access to the backend, and originate from an allowed proxy address.

Non-local bindings require native TLS or trusted proxy mode. Wildcard bindings such as `0.0.0.0` also require an HTTPS `HTTP_PUBLIC_URL` whose path matches `HTTP_PATH`.

See [Deployment Guide](DEPLOYMENT.md) for complete server, systemd, container, and Kubernetes examples.

## 10. Use the MCP tools

A typical read workflow is:

1. `repo_git_status`
2. `repo_list_files`
3. `repo_search_code`
4. `repo_read_file`
5. `repo_git_diff`

A typical write workflow is:

1. inspect the current file and Git status;
2. prepare one unified text patch;
3. call `repo_apply_patch`;
4. inspect the returned diff;
5. run `repo_git_status` and `repo_git_diff` again.

A typical test workflow is:

1. switch to `test` mode;
2. inspect the repository changes;
3. use an allowed `command_key` for one command, or `command_keys` for a batch, with `stop_on_failure` as needed;
4. review each command's `status`, `exit_code`, stdout, stderr, duration, and truncation indicators.

Local Repo MCP never commits or pushes the resulting changes.

## 11. Use the log center

Open **Logs** to view:

- **MCP** — server lifecycle, connection tests, HTTP process output, tool events, and allowlisted command start/finish status;
- **Tunnel** — Tunnel detection, initialization, Doctor, start, stop, and process output;
- **Audit** — repository operations and execution results;
- **Security** — denied authentication and permission-related events.

The log center supports:

- live refresh;
- keyword search;
- severity filtering;
- readable event summaries;
- raw JSON details;
- copying summaries or raw records.

Common Bearer tokens, API keys, and token query parameters are redacted before process output reaches the GUI.

Default rotation settings are:

```text
LOG_MAX_BYTES=5000000
LOG_BACKUP_COUNT=3
```

## 12. Configuration and log locations

### Windows

```text
%APPDATA%\LocalRepoMCP\config.json
%APPDATA%\LocalRepoMCP\secrets.json
%APPDATA%\LocalRepoMCP\mcp.jsonl
%APPDATA%\LocalRepoMCP\audit.jsonl
```

### Linux/macOS

```text
$XDG_CONFIG_HOME/local-repo-mcp/
```

When `XDG_CONFIG_HOME` is not set:

```text
~/.config/local-repo-mcp/
```

Normal settings and HTTP secrets are stored separately. The control-plane Runtime API Key is not persisted by the GUI.

## 13. Run the regression suite

From the source repository:

```bash
python -m pytest -q -p no:cacheprovider
```

Test counts change as the project evolves. Release verification uses the exit code and pass/skip/fail summary from the current full pytest run instead of a hard-coded count in documentation.

## 14. Troubleshooting

### Repository is rejected

Confirm that the path exists and is a Git working tree:

```bash
git -C /path/to/repository rev-parse --is-inside-work-tree
```

### Git is not found

Install Git and make sure `git --version` succeeds in the same environment that launches the GUI.

### STDIO shows no permanent running process

This is expected. STDIO starts per client session. Use **Connect** to verify it or configure an MCP client to launch the generated command.

### HTTP fails to start

Check the MCP log for:

- port already in use;
- invalid repository;
- missing Bearer token;
- invalid Host/Origin configuration;
- missing TLS certificate or key;
- non-local binding without TLS or trusted proxy mode;
- `HTTP_PUBLIC_URL` path mismatch.

### HTTP returns 401

Confirm that the client sends the exact configured Bearer token in the `Authorization` header.

### Tunnel executable is not found

Set the full path to `tunnel-client`, or add its directory to `PATH`, then run **Detect** again.

### Tunnel Doctor fails

Verify the Tunnel ID, profile, Runtime API Key, generated MCP command, and network access. Review the Tunnel log rather than copying secrets into issue reports.

### Search is slower without ripgrep

Local Repo MCP falls back to a bounded Python search when `rg` is unavailable. Installing ripgrep improves large-repository search performance but is not required.

### Test execution is denied

Confirm that the mode is `test` and that every `command_key` / `command_keys` entry is in the fixed allowlist. A batch containing any invalid key is rejected before execution begins.

## 15. Security checklist

Before using write, test, Tunnel, or remote HTTP modes:

- verify the selected repository path;
- start with `read` mode;
- enable `write` or `test` only when required;
- use only trusted repositories in `test` mode;
- keep HTTP tokens and Runtime API Keys private;
- do not expose plaintext HTTP remotely;
- configure explicit Host, Origin, public URL, and trusted proxy ranges;
- protect the configuration and log directory;
- review Git status and diff before committing changes manually.

See [Security Model](SECURITY.md) for the complete boundary.

## 16. Plain folders and Git initialization

The configured directory is the local project directory exposed to MCP clients. It may initially be a plain existing folder. Selecting it through Browse triggers an immediate Git check; a path typed manually is checked again before Connect or Start.

When the folder is not already in a Git working tree, the GUI asks for explicit confirmation before running `git init`. Declining leaves the folder unchanged. The operation creates only `.git` metadata and does not create a commit, configure a remote, or publish project files.

If the selected directory is already inside a parent Git working tree, Local Repo MCP uses that existing repository and does not create a nested `.git` directory. Git itself must still be installed and available on `PATH`.

The directory/Git-initialization behavior remains covered by regression tests; acceptance uses the current full test output.
