# Local Repo MCP 1.4.0 Delivery Notes

This revision keeps Local Repo MCP focused on its original lightweight single-repository role while making remote development verification reliable enough for build/test workflows.

Notable changes:

- Introduces one internal controlled-command abstraction (`CommandSpec` / registry / runner) for allowlisted test, build, lint, and check profiles; no arbitrary shell or task runtime is added.
- `repo_run_test` keeps its existing MCP tool name while supporting both one command and a bounded sequential batch of up to eight commands.
- Batch command keys are fully allowlist-validated before execution starts and may stop on the first failure or continue explicitly.
- Command results now carry normalized, verifiable `status`, `exit_code`, stdout/stderr, duration, timeout, and truncation evidence while preserving the legacy `returncode` field.
- Long-running verification commands emit lightweight start/finish log metadata; command output remains in the MCP result instead of audit logs.
- Unified patches are explicitly covered as atomic multi-file mutations, with regression coverage for all-or-nothing behavior.
- Remote Streamable HTTP supports native TLS/mTLS and trusted TLS reverse proxies.
- Container and Kubernetes wildcard bindings are supported with an explicit HTTPS public URL.
- GUI actions are now semantic: STDIO “Connect”; HTTP “Start/Stop”; both persist configuration automatically.
- Source and installed layouts share the packaged launcher.
- Search degrades safely when ripgrep is unavailable and remains output-bounded.
- Hard links are rejected and repository mutations use a shared cross-process Git-metadata lock.
- Malformed or wrong-shaped configuration files are quarantined.
- Windows HTTP tokens use current-user DPAPI with legacy plaintext migration.
- Startup readiness validates authentication and repository identity.
- Version metadata is unified at 1.4.0.

Run the full regression suite with:

```bash
python -m pytest -q -p no:cacheprovider
```

- Policy and environment denials are separated from permission-mode denials and include a visible reason.
- Write/test auditing is fail-closed, patch evidence is target-scoped, and test/search resource limits terminate safely.
- Native TLS readiness validates public SNI while connecting to the local listener.
- Wheel installation and execution are validated outside the source checkout.

