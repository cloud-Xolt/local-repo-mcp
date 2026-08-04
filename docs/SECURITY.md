# Security Architecture

## Repository confinement

All user paths are resolved relative to the configured repository. Absolute paths, `..`, symbolic links, sensitive paths, and hard-linked files are rejected. Git status and diff output are filtered through the same sensitive-path policy.

## Mutation model

Only `repo_apply_patch` can modify repository files. The server validates patch structure, target paths, existing target changes, credential-like additions, and `git apply --check` before applying. A cross-process advisory lock in the Git common directory serializes mutations across GUI, Tunnel, HTTP, and system services.

## HTTP boundary

Streamable HTTP requires a Bearer token for MCP and health endpoints. The authentication middleware is native ASGI and does not buffer streaming responses.

Remote exposure requires either native TLS or explicit TLS-proxy mode. Forwarded headers are trusted only from configured proxy IP addresses or networks. Host and Origin checks remain independent of TLS and authentication.

## Secrets

On Windows, the persisted HTTP token is protected with current-user DPAPI and legacy plaintext entries are migrated when read. On POSIX systems, configuration secret files are written atomically with restrictive permissions. Runtime control-plane API keys are kept in memory only.

## Test execution

`repo_run_test` runs only predefined command keys with a reduced environment, bounded timeout, external temporary directories, and bounded output. Test mode should be enabled only for repositories whose code is trusted.
