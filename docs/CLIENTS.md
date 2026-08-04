# ChatGPT and Other MCP Clients

[English](CLIENTS.md) | [简体中文](CLIENTS.zh-CN.md)

Local Repo MCP can be used by ChatGPT to build and maintain a local project, but it is not a ChatGPT-only integration. It is a general MCP server for one configured local Git working tree.

Any compatible MCP client, coding agent, IDE, desktop application, or automation platform can use the same tools through STDIO or Streamable HTTP.

## Build a local project with ChatGPT

Local Repo MCP requires the selected directory to be a Git working tree. To start a new project, create an empty directory and initialize Git:

```bash
mkdir my-project
cd my-project
git init
```

Then:

1. Start the Local Repo MCP GUI.
2. Select the new Git working tree.
3. Choose `write` mode when ChatGPT only needs to create and modify project files.
4. Choose `test` mode when ChatGPT also needs to run predefined test commands.
5. Choose a connection method.
6. Connect ChatGPT and request the project structure, source files, configuration, documentation, and tests that should be created.

Within the selected permission mode, ChatGPT can:

- inspect the repository structure;
- read allowed UTF-8 text files;
- search the codebase;
- create and modify files through validated unified patches;
- review filtered Git status and diff output;
- run predefined tests in `test` mode.

Local Repo MCP does not expose an unrestricted shell. It also does not allow arbitrary checkout, commit, reset, rebase, merge, pull, or push operations.

## Connect ChatGPT

ChatGPT-oriented deployments can use:

- **OpenAI Secure MCP Tunnel** for the GUI-managed STDIO Tunnel workflow;
- **Streamable HTTP** when the integration connects to a local or remote MCP endpoint.

The Secure MCP Tunnel page manages the Tunnel profile, Runtime API Key in process memory, Doctor checks, and Tunnel process lifecycle.

For Streamable HTTP, Bearer authentication is always required. Remote deployments must use native TLS/mTLS or an explicitly trusted TLS-terminating reverse proxy.

## Connect other MCP clients

Other MCP-compatible clients use the same server implementation and the same seven MCP tools.

### STDIO

Use STDIO when the client can launch Local Repo MCP as a child process. Copy the generated client configuration from the **MCP Server** page into the client.

STDIO is appropriate for:

- local coding agents;
- MCP-enabled IDEs;
- desktop MCP clients;
- local automation processes.

### Streamable HTTP

Use Streamable HTTP when the client connects to a long-running MCP endpoint.

The client must support:

- the configured MCP endpoint path;
- Bearer authorization;
- Streamable HTTP;
- TLS certificate validation for HTTPS deployments;
- a client certificate when mTLS is enabled.

The same endpoint can be used by different compatible clients, but Local Repo MCP remains a single-user tool for one configured repository. It is not a multi-tenant authorization service.

## Same tools and controls for every client

Client identity does not change the server capability set. ChatGPT and other MCP clients receive the same tools:

| Tool | Capability |
| --- | --- |
| `repo_list_files` | List allowed repository files. |
| `repo_read_file` | Read an allowed UTF-8 text file. |
| `repo_search_code` | Search using a bounded fixed string. |
| `repo_git_status` | Read filtered Git status. |
| `repo_git_diff` | Read a bounded, filtered Git diff. |
| `repo_apply_patch` | Apply a validated unified text patch. |
| `repo_run_test` | Run one predefined test command in `test` mode. |

Every client is subject to the same:

- configured repository root;
- permission mode;
- path traversal, symbolic-link, hard-link, and sensitive-path controls;
- input, output, search, file, patch, and test limits;
- Patch validation and dirty-target protection;

## Folder selection and Git initialization

Manual `git init` is optional. When a user selects a plain folder, the GUI checks it immediately and asks for explicit confirmation before initializing it. The same check runs again before Connect or Start when the path was entered manually.

Declining the prompt leaves the folder unchanged. Initialization creates only local `.git` metadata; Local Repo MCP does not create a commit, configure a remote, or publish the project. A child folder already inside an existing Git working tree is accepted without creating a nested repository.

Git itself must still be installed and available on `PATH`, because repository status, diff, patch validation, and mutation locking depend on Git.
