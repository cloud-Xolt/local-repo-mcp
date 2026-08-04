# Local Repo MCP 1.3.0 Delivery Notes

This revision hardens remote deployment, configuration consistency, repository confinement, process lifecycle, search behavior, Tunnel portability, package installation, and GUI action semantics.

Notable changes:

- Remote Streamable HTTP supports native TLS/mTLS and trusted TLS reverse proxies.
- Container and Kubernetes wildcard bindings are supported with an explicit HTTPS public URL.
- GUI actions are now semantic: STDIO “Connect”; HTTP “Start/Stop”; both persist configuration automatically.
- Source and installed layouts share the packaged launcher.
- Search degrades safely when ripgrep is unavailable and remains output-bounded.
- Hard links are rejected and repository mutations use a shared cross-process Git-metadata lock.
- Malformed or wrong-shaped configuration files are quarantined.
- Windows HTTP tokens use current-user DPAPI with legacy plaintext migration.
- Startup readiness validates authentication and repository identity.
- Version metadata is unified at 1.3.0.

Run the full regression suite with:

```bash
python -m pytest -q -p no:cacheprovider
```

- Policy and environment denials are separated from permission-mode denials and include a visible reason.
- Write/test auditing is fail-closed, patch evidence is target-scoped, and test/search resource limits terminate safely.
- Native TLS readiness validates public SNI while connecting to the local listener.
- Wheel installation and execution are validated outside the source checkout.

