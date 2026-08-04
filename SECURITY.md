# Security Policy

Local Repo MCP exposes one explicitly configured Git working tree. It is not a general shell, multi-user agent runtime, or sandbox for untrusted code.

## Security boundary

- Repository paths reject absolute paths, parent traversal, symbolic links, sensitive paths, and multi-link files.
- Reads, search results, Git output, HTTP requests, patches, and test output are bounded.
- Writes are accepted only as validated unified text patches.
- Repository mutations use a cross-process lock stored in shared Git metadata.
- Streamable HTTP always requires Bearer authentication.
- Remote HTTP requires native TLS or an explicitly configured trusted TLS reverse proxy.
- Proxy headers are accepted only from `HTTP_PROXY_TRUSTED_IPS`.
- Windows stores the HTTP token with current-user DPAPI; POSIX secret files use restrictive permissions.
- Control-plane Runtime API keys are not persisted by the GUI.

## Trusted test execution

Test mode executes predefined commands from the selected repository with the current user's operating-system permissions. It is not sandboxed. Enable test mode only for repositories whose code and test configuration you trust.

Runtime logs are operational diagnostics. Audit logs are security metadata. Both are bounded and rotated, but operators must protect the configured log directory and apply their normal retention policy.

## Reporting

Report security issues privately to the repository maintainer. Do not include live credentials, customer data, or exploit output in public issues.
